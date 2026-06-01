import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple
from app.core.ocr_helpers import extract_digital_pdf_text, run_ocr_sync
import easyocr  
logger = logging.getLogger("certificate_intelligence.ocr")

class OCREngine:
    _instance = None
    _ocr_engine = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(OCREngine, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def _get_easy_ocr(self):
        """Lazily initialize EasyOCR only when needed to prevent high startup delay."""
        if self._ocr_engine is None:
            logger.info("Initializing EasyOCR engine (lazy-loading)...")
            try:
                import easyocr
                try:

                    logger.info("Attempting to load EasyOCR with English and Tamil ['en', 'ta']...")
                    self._ocr_engine = easyocr.Reader(['en', 'ta'])
                except Exception as ex:
                    logger.warning(f"Failed to load English/Tamil EasyOCR (possible size mismatch): {ex}. Falling back to English only ['en']...")
                    self._ocr_engine = easyocr.Reader(['en'])
                logger.info("EasyOCR engine loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                raise RuntimeError(f"Could not load EasyOCR. Details: {e}")
        return self._ocr_engine

    async def extract_text(self, file_path: Path) -> Tuple[str, str]:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # --- Path 1: Fast-path for PDF digital text layer ---
        if file_path.suffix.lower() == ".pdf":
            digital_text = extract_digital_pdf_text(file_path)
            if digital_text: return digital_text, "Digital PDF Text"

        # --- Path 2: CPU-heavy EasyOCR in threadpool ---
        loop = asyncio.get_running_loop()
        try:
           
            ocr_reader = self._get_easy_ocr()
            raw_ocr_text = await loop.run_in_executor(None, run_ocr_sync, file_path, ocr_reader)
            return raw_ocr_text, "EasyOCR"
        except (ImportError, Exception) as e:
            logger.error(f"OCR Engine failed: {e}")
            return "", "None (All Methods Failed)"

_ocr_engine_instance = OCREngine()

def get_ocr_engine() -> OCREngine:
    return _ocr_engine_instance
