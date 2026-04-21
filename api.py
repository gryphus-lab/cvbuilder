from typing import Annotated
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import asyncio
import uuid
import main  # Import our updated main.py

app = FastAPI()
UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/healthz")
async def healthz():
    """Health check endpoint for container orchestrators."""
    return {"status": "ok"}


@app.post("/parse")
async def api_parse(file: Annotated[UploadFile, File(...)]):
    # Create unique per-request temp path
    """
    Parse an uploaded PDF and return the extracted structured data.
    
    Writes the upload to a temporary file, invokes the parser on that file, and ensures the temporary file is removed afterwards. Non-HTTP exceptions are converted to an HTTP 500 error; existing HTTPException instances are re-raised unchanged.
    
    Returns:
        Parsed data (typically a dict) produced from the uploaded PDF.
    """
    temp_pdf = UPLOAD_DIR / f"temp_{uuid.uuid4()}.pdf"
    try:
        loop = asyncio.get_running_loop()

        def _save():
            """
            Write the uploaded file's raw bytes to the temporary PDF path.
            
            This helper reads from the outer-scope `file` object's file stream and writes its contents to the outer-scope `temp_pdf` path, creating or overwriting the file on disk.
            """
            with open(temp_pdf, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

        await loop.run_in_executor(None, _save)
        data = await loop.run_in_executor(None, main.run_parse, temp_pdf)
        return data
    except HTTPException:
        # Re-raise HTTPException unchanged
        raise
    except Exception as e:
        # Chain other exceptions
        raise HTTPException(status_code=500, detail=f"Parse Error: {e!s}") from e
    finally:
        if temp_pdf.exists():
            temp_pdf.unlink()


@app.post("/build")
async def api_build(
    cv_data: dict, background_tasks: BackgroundTasks
):  # Add background_tasks
    """
    Generate a PDF CV from structured data and return it as a downloadable FileResponse.
    
    Creates a unique PDF in the results directory using the provided `cv_data`, returns a FileResponse serving that PDF with filename "my_cv.pdf" and media type "application/pdf", and schedules deletion of the generated file after the response is sent.
    
    Parameters:
        cv_data (dict): Structured CV data used to populate the generated PDF.
        background_tasks (BackgroundTasks): FastAPI BackgroundTasks instance used to schedule post-response cleanup.
    
    Returns:
        FileResponse: A response streaming the generated PDF file to the client.
    
    Raises:
        HTTPException: With status 500 if PDF generation fails or an internal error occurs; any incoming HTTPException is re-raised unchanged.
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
        raise
    except Exception as e:
        # If we failed before returning the response, clean up now
        if output_pdf_path.exists():
            output_pdf_path.unlink()
        raise HTTPException(status_code=500, detail=f"Builder Error: {e!s}") from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8080)