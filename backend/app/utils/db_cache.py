import logging
import json
from typing import Optional, Dict, Any
from app.models.database import SessionLocal, OCRCache, PipelineCache

logger = logging.getLogger("certificate_intelligence.cache")

class DatabaseCache:
    def __init__(self, db_path: str = None):
        pass

    def get_ocr(self, file_hash: str) -> Optional[str]:
        """Retrieve raw OCR text from the cache using a file hash."""
        db = SessionLocal()
        try:
            record = db.query(OCRCache).filter(OCRCache.file_hash == file_hash).first()
            if record:
                logger.info(f"OCR Cache HIT for hash: {file_hash}")
                return record.raw_text
            return None
        except Exception as e:
            logger.error(f"Error fetching from OCR cache: {e}")
            return None
        finally:
            db.close()

    def save_ocr(self, file_hash: str, raw_text: str):
        """Save raw OCR text to the cache."""
        db = SessionLocal()
        try:
            record = db.query(OCRCache).filter(OCRCache.file_hash == file_hash).first()
            if record: record.raw_text = raw_text
            else: db.add(OCRCache(file_hash=file_hash, raw_text=raw_text))
            db.commit()
            logger.info(f"Saved OCR result to cache for hash: {file_hash}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving to OCR cache: {e}")
        finally:
            db.close()

    def get_pipeline(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve full pipeline response JSON from the cache (Duplicate Detection)."""
        db = SessionLocal()
        try:
            record = db.query(PipelineCache).filter(PipelineCache.file_hash == file_hash).first()
            if record:
                logger.info(f"Pipeline Cache HIT (Duplicate detected) for hash: {file_hash}")
                return json.loads(record.result_json)
            return None
        except Exception as e:
            logger.error(f"Error fetching from pipeline cache: {e}")
            return None
        finally:
            db.close()

    def save_pipeline(self, file_hash: str, result_dict: Dict[str, Any]):
        """Save full pipeline response JSON to the cache."""
        db = SessionLocal()
        try:
            result_json = json.dumps(result_dict)
            record = db.query(PipelineCache).filter(PipelineCache.file_hash == file_hash).first()
            if record: record.result_json = result_json
            else: db.add(PipelineCache(file_hash=file_hash, result_json=result_json))
            db.commit()
            logger.info(f"Saved pipeline analysis to cache for hash: {file_hash}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving to pipeline cache: {e}")
        finally:
            db.close()

    def clear_all(self) -> int:
        """Delete all entries from both OCR and pipeline cache tables. Returns total rows deleted."""
        db = SessionLocal()
        try:
            total = db.query(PipelineCache).delete() + db.query(OCRCache).delete()
            db.commit()
            logger.info(f"Cache cleared — {total} total entries removed.")
            return total
        except Exception as e:
            db.rollback()
            logger.error(f"Error clearing cache: {e}")
            return 0
        finally:
            db.close()

cache_db = None

def get_cache(db_path: str = None) -> DatabaseCache:
    global cache_db
    if cache_db is None: cache_db = DatabaseCache()
    return cache_db
