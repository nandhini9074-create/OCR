import logging
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pathlib import Path
from typing import Optional

from app.utils.file_handler import FileHandler
from app.core.pipeline import get_pipeline
from app.schemas.models import AnalysisResponse

logger = logging.getLogger("certificate_intelligence.routes")
router = APIRouter()
file_handler, pipeline = FileHandler(), get_pipeline()

OCR_TEMP_DIR = Path(__file__).resolve().parents[2] / "temp"
OCR_TEMP_FILE = OCR_TEMP_DIR / "ocr_preview.txt"

def _write_ocr_temp_file(raw_text: str, method: str, filename: str) -> None:
    OCR_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    if OCR_TEMP_FILE.exists(): OCR_TEMP_FILE.unlink()
    content = f"=== OCR PREVIEW FILE ===\nSource File  : {filename}\nMethod Used  : {method}\n{'=' * 40}\n\n{raw_text}\n"
    OCR_TEMP_FILE.write_text(content, encoding="utf-8")
    logger.info(f"OCR preview temp file written: {OCR_TEMP_FILE}")

@router.post("/analyze-certificate", response_model=AnalysisResponse, status_code=200, summary="Upload and Analyze Certificate")
async def analyze_certificate(file: UploadFile = File(..., description="The certificate image or PDF"), email: Optional[str] = Form(None)):
    logger.info(f"Received file upload request: {file.filename} with email: {email}")
    try:
        file_path, file_hash = await file_handler.save_file(file)
        res = await pipeline.analyze_certificate(file_path=file_path, file_hash=file_hash, email=email)
        _write_ocr_temp_file(res.raw_ocr_text or "(No text extracted)", res.ocr_method or "Unknown", file.filename)
        return res
    except HTTPException as he: raise he
    except Exception as e:
        logger.critical(f"Unhandled critical error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.get("/ocr-preview", summary="Get Raw OCR Preview")
async def get_ocr_preview():
    if not OCR_TEMP_FILE.exists():
        raise HTTPException(status_code=404, detail="No OCR preview available. Submit a certificate first.")
    try:
        lines = OCR_TEMP_FILE.read_text(encoding="utf-8").splitlines()
        source_file = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("Source File  :")), "")
        method = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("Method Used  :")), "")
        return {"source_file": source_file, "method": method, "raw_text": "\n".join(lines[4:]).strip() if len(lines) > 4 else "", "temp_file_path": str(OCR_TEMP_FILE)}
    except Exception as e:
        logger.error(f"Failed to read OCR temp file: {e}")
        raise HTTPException(status_code=500, detail=f"Could not read OCR preview: {str(e)}")

@router.delete("/clear-cache", summary="Clear Analysis Cache")
async def clear_cache():
    try:
        from app.utils.db_cache import get_cache
        removed = get_cache().clear_all()
        if OCR_TEMP_FILE.exists(): OCR_TEMP_FILE.unlink()
        logger.info(f"Cache cleared via API — {removed} entries removed.")
        return {"status": "cleared", "entries_removed": removed, "message": f"Successfully cleared {removed} cache entries. Next upload will run fresh OCR."}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=f"Cache clear failed: {str(e)}")
