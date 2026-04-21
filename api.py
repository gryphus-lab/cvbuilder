from fastapi import FastAPI, BackgroundTasks, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import asyncio
import uuid
import main  # Import our updated main.py

app = FastAPI()
UPLOAD_DIR = Path("results")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/parse")
async def api_parse(file: UploadFile = File(...)):
    # Create unique per-request temp path
    """
    Parse an uploaded PDF file and return the extracted data.

    The upload is written to a temporary file which is removed after processing. Re-raises HTTPException unchanged; other exceptions are converted to an HTTP 500 error.

    Returns:
        Parsed data produced from the uploaded PDF (typically a dict).
    """
    temp_pdf = UPLOAD_DIR / f"temp_{uuid.uuid4()}_{file.filename}"
    try:
        with open(temp_pdf, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Offload blocking call to threadpool
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, main.run_parse, temp_pdf)
        return data
    except HTTPException:
        # Re-raise HTTPException unchanged
        raise
    except Exception as e:
        # Chain other exceptions
        raise HTTPException(status_code=500, detail=f"Parse Error: {str(e)}") from e
    finally:
        if temp_pdf.exists():
            temp_pdf.unlink()




@app.post("/build")
async def api_build(
    cv_data: dict, background_tasks: BackgroundTasks
):  # Add background_tasks
    output_pdf_path = RESULTS_DIR / f"generated_cv_{uuid.uuid4()}.pdf"
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, main.run_build_from_data, cv_data, output_pdf_path, None
        )

        if not output_pdf_path.exists():
            raise HTTPException(status_code=500, detail="PDF generation failed.")

        # Schedule the cleanup to happen AFTER the response is sent
        background_tasks.add_task(
            lambda p: p.unlink() if p.exists() else None, output_pdf_path
        )

        return FileResponse(
            path=output_pdf_path, filename="my_cv.pdf", media_type="application/pdf"
        )
    except Exception as e:
        # If we failed before returning the response, clean up now
        if output_pdf_path.exists():
            output_pdf_path.unlink()
        raise HTTPException(status_code=500, detail=f"Builder Error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8080)
