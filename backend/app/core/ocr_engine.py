import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple
from pypdf import PdfReader

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
                # Initialize EasyOCR with English and Tamil languages for handwritten and printed text
                self._ocr_engine = easyocr.Reader(['en', 'ta'])
                logger.info("EasyOCR engine loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                raise RuntimeError(
                    f"Could not load EasyOCR. Ensure easyocr is installed. Details: {e}"
                )
        return self._ocr_engine

    def _extract_digital_pdf_text(self, pdf_path: Path) -> Optional[str]:
        """Attempt to extract native text layers from digital PDFs (fast path)."""
        try:
            logger.info(f"Checking digital text layer for PDF: {pdf_path.name}")
            reader = PdfReader(pdf_path)
            full_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    full_text.append(text)
            
            combined_text = "\n".join(full_text).strip()
            # If we found sufficient text, we return it
            if len(combined_text) > 40:
                logger.info(f"Digital text successfully extracted from PDF ({len(combined_text)} chars). Skipping OCR.")
                return combined_text
            else:
                logger.info("Digital text layer was empty or too short. Falling back to OCR.")
        except Exception as e:
            logger.warning(f"Error checking digital PDF text layer: {e}. Falling back to OCR.")
        return None

    def _run_ocr_sync(self, file_path: Path) -> str:
        """Synchronous method to run EasyOCR on an image or scanned PDF."""
        ocr = self._get_easy_ocr()
        file_str_path = str(file_path.resolve())
        logger.info(f"Running EasyOCR on file: {file_path.name}")
        
        try:
            # easyocr readtext() returns a list of tuples (bbox, text, prob)
            result = ocr.readtext(file_str_path)
            if not result:
                logger.warning("EasyOCR returned empty results.")
                return ""
            
            extracted_lines = [item[1] for item in result]
            
            raw_text = "\n".join(extracted_lines).strip()
            logger.info(f"EasyOCR completed. Extracted {len(extracted_lines)} lines ({len(raw_text)} characters).")
            return raw_text
        except Exception as e:
            logger.error(f"Error executing EasyOCR on {file_path.name}: {e}")
            raise RuntimeError(f"OCR execution failed: {e}")


    async def extract_text(self, file_path: Path) -> Tuple[str, str]:
        """
        Asynchronously extract text from an uploaded certificate.
        Returns a tuple: (raw_text, method_name)
        Methods tried in order:
          1. Digital PDF Text  (fast path for native-text PDFs)
          2. EasyOCR           (image / scanned PDF OCR)
          3. Groq Vision       (LLM-based multimodal fallback)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # --- Path 1: Fast-path for PDF digital text layer ---
        if file_path.suffix.lower() == ".pdf":
            digital_text = self._extract_digital_pdf_text(file_path)
            if digital_text:
                return digital_text, "Digital PDF Text"

        # --- Path 2: CPU-heavy EasyOCR in threadpool ---
        loop = asyncio.get_running_loop()
        try:
            import easyocr  # noqa: F401 — presence check
            raw_ocr_text = await loop.run_in_executor(None, self._run_ocr_sync, file_path)
            return raw_ocr_text, "EasyOCR"
        except (ImportError, Exception) as e:
            logger.error(f"OCR Engine failed: {e}")
            logger.warning("Returning empty OCR text to allow pipeline to continue.")
            return "", "None (All Methods Failed)"

# Singleton helper
_ocr_engine_instance = OCREngine()

def get_ocr_engine() -> OCREngine:
    return _ocr_engine_instance

