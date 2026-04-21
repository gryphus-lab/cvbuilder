from fastapi import FastAPI, UploadFile, File, HTTPException
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
async def api_build(cv_data: dict):
    """
    Takes JSON data, uses CVBuilder to create a PDF,
    and returns the actual PDF file to the browser.
    """
    # Create unique per-request output path
    output_pdf_path = RESULTS_DIR / f"generated_cv_{uuid.uuid4()}.pdf"

    try:
        # Offload blocking call to threadpool
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, main.run_build_from_data, cv_data, output_pdf_path, None)

        # Check if the file was actually created by CVBuilder
        if not output_pdf_path.exists():
            raise HTTPException(status_code=500, detail="PDF generation failed.")

        # Return the file so the browser downloads it
        return FileResponse(
            path=output_pdf_path, filename="my_cv.pdf", media_type="application/pdf"
        )

    except HTTPException:
        # Re-raise HTTPException unchanged
        raise
    except Exception as e:
        # Chain other exceptions
        raise HTTPException(status_code=500, detail=f"Builder Error: {str(e)}") from e
    finally:
        # Clean up per-request file
        if output_pdf_path.exists():
            output_pdf_path.unlink()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)