import os
import sqlite3
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("certificate_intelligence.cache")

class DatabaseCache:
    def __init__(self, db_path: str = "./cache/metadata_cache.db"):
        self.db_path = db_path
        # Ensure the directory for the DB exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize the SQLite database with OCR and Pipeline caching tables."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Table for caching OCR results
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ocr_cache (
                        file_hash TEXT PRIMARY KEY,
                        raw_text TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Table for caching full pipeline responses (duplicate certificate detection)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pipeline_cache (
                        file_hash TEXT PRIMARY KEY,
                        result_json TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                logger.info("SQLite caching database initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing SQLite database: {e}")

    def get_ocr(self, file_hash: str) -> Optional[str]:
        """Retrieve raw OCR text from the cache using a file hash."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT raw_text FROM ocr_cache WHERE file_hash = ?", (file_hash,))
                row = cursor.fetchone()
                if row:
                    logger.info(f"OCR Cache HIT for hash: {file_hash}")
                    return row["raw_text"]
        except Exception as e:
            logger.error(f"Error fetching from OCR cache: {e}")
        return None

    def save_ocr(self, file_hash: str, raw_text: str):
        """Save raw OCR text to the cache."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO ocr_cache (file_hash, raw_text) VALUES (?, ?)",
                    (file_hash, raw_text)
                )
                conn.commit()
                logger.info(f"Saved OCR result to cache for hash: {file_hash}")
        except Exception as e:
            logger.error(f"Error saving to OCR cache: {e}")

    def get_pipeline(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve full pipeline response JSON from the cache (Duplicate Detection)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT result_json FROM pipeline_cache WHERE file_hash = ?", (file_hash,))
                row = cursor.fetchone()
                if row:
                    logger.info(f"Pipeline Cache HIT (Duplicate detected) for hash: {file_hash}")
                    return json.loads(row["result_json"])
        except Exception as e:
            logger.error(f"Error fetching from pipeline cache: {e}")
        return None

    def save_pipeline(self, file_hash: str, result_dict: Dict[str, Any]):
        """Save full pipeline response JSON to the cache."""
        try:
            result_json = json.dumps(result_dict)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO pipeline_cache (file_hash, result_json) VALUES (?, ?)",
                    (file_hash, result_json)
                )
                conn.commit()
                logger.info(f"Saved pipeline analysis to cache for hash: {file_hash}")
        except Exception as e:
            logger.error(f"Error saving to pipeline cache: {e}")

    def clear_all(self) -> int:
        """Delete all entries from both OCR and pipeline cache tables. Returns total rows deleted."""
        total = 0
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM pipeline_cache")
                total += cursor.rowcount
                cursor.execute("DELETE FROM ocr_cache")
                total += cursor.rowcount
                conn.commit()
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
