from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Float, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship
from app.models.base import Base

class EmailMetadata(Base):
    __tablename__ = "email_metadata"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    email_id = Column(String, nullable=False, index=True)
    thread_id = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    sender = Column(String, nullable=True)
    recipients = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    importance_score = Column(Float, default=0.0)
    synced_at = Column(DateTime, default=datetime.utcnow)
    body = Column(Text, nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)

    user = relationship("User", back_populates="emails")

    __table_args__ = (
        Index("email_search_idx", "search_vector", postgresql_using="gin"),
    )

class SyncLog(Base):
    __tablename__ = "sync_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    status = Column(String, nullable=False)  # 'running', 'completed', 'failed'
    emails_synced = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text, nullable=True)
