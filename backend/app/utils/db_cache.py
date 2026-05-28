import json
import logging
from typing import Optional, Dict, Any
from app.models.database import SessionLocal, OCRCache, PipelineCache

logger = logging.getLogger("certificate_intelligence.cache")

class DatabaseCache:
    def __init__(self, db_path: str = "./cache/metadata_cache.db"):
        # Database initialization is now handled globally by init_db() in main.py
        pass

    def get_ocr(self, file_hash: str) -> Optional[str]:
        """Retrieve raw OCR text from the cache using a file hash."""
        try:
            with SessionLocal() as db:
                result = db.query(OCRCache).filter(OCRCache.file_hash == file_hash).first()
                if result:
                    logger.info(f"OCR Cache HIT for hash: {file_hash}")
                    return result.raw_text
        except Exception as e:
            logger.error(f"Error fetching from OCR cache: {e}")
        return None

    def save_ocr(self, file_hash: str, raw_text: str):
        """Save raw OCR text to the cache."""
        try:
            with SessionLocal() as db:
                obj = db.query(OCRCache).filter(OCRCache.file_hash == file_hash).first()
                if obj:
                    obj.raw_text = raw_text
                else:
                    obj = OCRCache(file_hash=file_hash, raw_text=raw_text)
                    db.add(obj)
                db.commit()
                logger.info(f"Saved OCR result to cache for hash: {file_hash}")
        except Exception as e:
            logger.error(f"Error saving to OCR cache: {e}")

    def get_pipeline(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve full pipeline response JSON from the cache (Duplicate Detection)."""
        try:
            with SessionLocal() as db:
                result = db.query(PipelineCache).filter(PipelineCache.file_hash == file_hash).first()
                if result:
                    logger.info(f"Pipeline Cache HIT (Duplicate detected) for hash: {file_hash}")
                    return json.loads(result.result_json)
        except Exception as e:
            logger.error(f"Error fetching from pipeline cache: {e}")
        return None

    def save_pipeline(self, file_hash: str, result_dict: Dict[str, Any]):
        """Save full pipeline response JSON to the cache."""
        try:
            result_json = json.dumps(result_dict)
            with SessionLocal() as db:
                obj = db.query(PipelineCache).filter(PipelineCache.file_hash == file_hash).first()
                if obj:
                    obj.result_json = result_json
                else:
                    obj = PipelineCache(file_hash=file_hash, result_json=result_json)
                    db.add(obj)
                db.commit()
                logger.info(f"Saved pipeline analysis to cache for hash: {file_hash}")
        except Exception as e:
            logger.error(f"Error saving to pipeline cache: {e}")

    def clear_all(self) -> int:
        """Delete all entries from both OCR and pipeline cache tables. Returns total rows deleted."""
        total = 0
        try:
            with SessionLocal() as db:
                total += db.query(PipelineCache).delete()
                total += db.query(OCRCache).delete()
                db.commit()
                logger.info(f"Cache cleared — {total} total entries removed.")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
        return total

# Global cache instance
cache_db = None

def get_cache(db_path: str = "./cache/metadata_cache.db") -> DatabaseCache:
    global cache_db
    if cache_db is None:
        cache_db = DatabaseCache(db_path)
    return cache_db
