from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import main  # Import our updated main.py

app = FastAPI()
UPLOAD_DIR = Path("results")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/parse")
async def api_parse(file: UploadFile = File(...)):
    temp_pdf = UPLOAD_DIR / f"temp_{file.filename}"
    try:
        with open(temp_pdf, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Call logic from main.py
        data = main.run_parse(temp_pdf)
        return data
    finally:
        if temp_pdf.exists():
            temp_pdf.unlink()


@app.post("/build")
async def api_build(cv_data: dict):
    """
    Takes JSON data, uses CVBuilder to create a PDF,
    and returns the actual PDF file to the browser.
    """
    output_pdf_path = RESULTS_DIR / "generated_cv.pdf"

    try:
        # We call the logic function in main.py
        # Which looks like: run_build(data, output_path)
        main.run_build_from_data(cv_data, output_pdf_path)

        # Check if the file was actually created by CVBuilder
        if not output_pdf_path.exists():
            raise HTTPException(status_code=500, detail="PDF generation failed.")

        # Return the file so the browser downloads it
        return FileResponse(
            path=output_pdf_path, filename="my_cv.pdf", media_type="application/pdf"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Builder Error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
