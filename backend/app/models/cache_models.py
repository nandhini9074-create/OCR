from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from app.models.base import Base

class OCRCache(Base):
    __tablename__ = "ocr_cache"
    file_hash = Column(String, primary_key=True)
    raw_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class PipelineCache(Base):
    __tablename__ = "pipeline_cache"
    file_hash = Column(String, primary_key=True)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
