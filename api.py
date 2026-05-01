from typing import Annotated
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import asyncio
import uuid
from pdf2image.exceptions import (
    PDFPageCountError,
    PDFSyntaxError,
    PopplerNotInstalledError,
    PDFInfoNotInstalledError,
    PDFPopplerTimeoutError,
)
import main  # Import our updated main.py

app = FastAPI()
UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/healthz")
async def healthz():
    """
    Health check endpoint used by orchestration and monitoring systems.

    Returns:
        dict: Mapping `{"status": "ok"}` indicating the service is healthy.
    """
    return {"status": "ok"}


@app.post(
    "/parse",
    responses={
        "400": {
            "description": "Bad Request - Invalid PDF file",
            "content": {"application/json": {"example": {"detail": "string"}}},
        },
        "500": {
            "description": "Internal Server Error",
            "content": {"application/json": {"example": {"detail": "string"}}},
        }
    },
)
async def api_parse(file: Annotated[UploadFile, File(...)]):
    """
    Parse an uploaded PDF and return structured data extracted from it.

    The uploaded file is written to a temporary PDF and passed to the parser; the temporary file is removed before returning. If the file is not a valid PDF, returns 400. If the parser raises an `HTTPException` it is re-raised unchanged; other exceptions are converted to an `HTTPException` with status code 500 and a `"Parse Error: ..."` detail.

    Returns:
        Parsed data (typically a dict) extracted from the uploaded PDF.
    """
    temp_pdf = UPLOAD_DIR / f"temp_{uuid.uuid4()}.pdf"
    try:
        loop = asyncio.get_running_loop()

        def _save():
            """
            Write the uploaded file stream to the temporary PDF path, creating or overwriting the file on disk.

            This helper persists the incoming upload to `temp_pdf`. It does not return a value.
            """
            with open(temp_pdf, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

        await loop.run_in_executor(None, _save)
        data = await loop.run_in_executor(None, main.run_parse, temp_pdf)
        return data
    except HTTPException:
        # Re-raise HTTPException unchanged
        raise
    except (PDFPageCountError, PDFSyntaxError) as e:
        # Invalid PDF file errors
        raise HTTPException(status_code=400, detail=f"Invalid PDF file: {str(e)}") from e
    except (PopplerNotInstalledError, PDFInfoNotInstalledError, PDFPopplerTimeoutError) as e:
        # Environment/server configuration errors
        raise HTTPException(status_code=500, detail=f"Server configuration error: {str(e)}") from e
    except Exception as e:
        # Generic parse errors
        raise HTTPException(status_code=500, detail=f"Parse Error: {str(e)}") from e
    finally:
        temp_pdf.unlink(missing_ok=True)


@app.post(
    "/build",
    responses={
        "500": {
            "description": "Internal Server Error",
            "content": {"application/json": {"example": {"detail": "string"}}},
        }
    },
)
async def api_build(
    cv_data: dict, background_tasks: BackgroundTasks
):
    """
    Generate a PDF CV from structured input data.

    Creates a uniquely named PDF in the module's results directory using `cv_data`, schedules the generated file for deletion after the response is sent, and returns a downloadable PDF response named "my_cv.pdf".

    Parameters:
        cv_data (dict): Structured CV content used to populate the generated PDF.
        background_tasks (BackgroundTasks): FastAPI BackgroundTasks used to schedule post-response cleanup of the generated file.

    Returns:
        FileResponse: A response streaming the generated PDF file with filename "my_cv.pdf" and media type "application/pdf".

    Raises:
        HTTPException: Re-raises any incoming `HTTPException` unchanged. If PDF generation fails or an internal error occurs, deletes any partially created file and raises `HTTPException(status_code=500, detail="Builder Error: <error>")`.
    """
    output_pdf_path = RESULTS_DIR / f"generated_cv_{uuid.uuid4()}.pdf"
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, main.run_build_from_data, cv_data, output_pdf_path, None
        )

        if not output_pdf_path.exists():
            raise HTTPException(status_code=500, detail="PDF generation failed.")

        # Schedule the cleanup to happen AFTER the response is sent
        background_tasks.add_task(output_pdf_path.unlink, missing_ok=True)

        return FileResponse(
            path=output_pdf_path, filename="my_cv.pdf", media_type="application/pdf"
        )
    except HTTPException:
        # Re-raise HTTPException unchanged
        output_pdf_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        # If we failed before returning the response, clean up now
        output_pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Builder Error: {e!s}") from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8080)
