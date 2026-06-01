import logging
import re
from pathlib import Path
from typing import Optional
from pypdf import PdfReader

logger = logging.getLogger("certificate_intelligence.ocr_helpers")

def clean_ocr_text(raw_text: str) -> str:
    """Programmatically clean raw OCR text from junk characters, noise, and whitespace anomalies."""
    if not raw_text: return ""
    lines = raw_text.splitlines()
    cleaned_lines = []
    for line in lines:
        cleaned = line.strip()
        # Remove trailing/leading OCR junk characters
        cleaned = re.sub(r'^[\s_\|\~\*\\\/]+', '', cleaned)
        cleaned = re.sub(r'[\s_\|\~\*\\\/]+$', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if cleaned: cleaned_lines.append(cleaned)
    return "\n".join(cleaned_lines)

def extract_digital_pdf_text(pdf_path: Path) -> Optional[str]:
    """Attempt to extract native text layers from digital PDFs (fast path)."""
    try:
        logger.info(f"Checking digital text layer for PDF: {pdf_path.name}")
        reader = PdfReader(pdf_path)
        full_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text: full_text.append(text)
        
        combined_text = "\n".join(full_text).strip()
        if len(combined_text) > 40:
            logger.info(f"Digital text successfully extracted from PDF ({len(combined_text)} chars). Skipping OCR.")
            return clean_ocr_text(combined_text)
        else:
            logger.info("Digital text layer was empty or too short. Falling back to OCR.")
    except Exception as e:
        logger.warning(f"Error checking digital PDF text layer: {e}. Falling back to OCR.")
    return None

def run_ocr_sync(file_path: Path, ocr_reader) -> str:
    """Synchronous method to run EasyOCR on an image or scanned PDF."""
    file_str_path = str(file_path.resolve())
    logger.info(f"Running EasyOCR on file: {file_path.name}")
    try:
        result = ocr_reader.readtext(file_str_path)
        if not result:
            logger.warning("EasyOCR returned empty results.")
            return ""
        
        extracted_lines = [item[1] for item in result]
        raw_text = "\n".join(extracted_lines).strip()
        logger.info(f"EasyOCR completed. Extracted {len(extracted_lines)} lines ({len(raw_text)} characters).")
        return clean_ocr_text(raw_text)
    except Exception as e:
        logger.error(f"Error executing EasyOCR on {file_path.name}: {e}")
        raise RuntimeError(f"OCR execution failed: {e}")

