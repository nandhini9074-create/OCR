import os
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from app.utils.encryption import get_encryptor

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    user_id = Column(String, primary_key=True, index=True)  # Can be their email address
    created_at = Column(DateTime, default=datetime.utcnow)
    tokens = relationship("OAuthToken", back_populates="user", cascade="all, delete-orphan")
    emails = relationship("EmailMetadata", back_populates="user", cascade="all, delete-orphan")

class OAuthToken(Base):
    __tablename__ = "oauth_tokens"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    provider = Column(String, nullable=False)  # 'google' or 'microsoft'
    email = Column(String, nullable=False)     # Authorized inbox email address
    _access_token = Column("access_token", Text, nullable=False)
    _refresh_token = Column("refresh_token", Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tokens")

    @property
    def access_token(self) -> str:
        return get_encryptor().decrypt(self._access_token)

    @access_token.setter
    def access_token(self, val: str):
        self._access_token = get_encryptor().encrypt(val)

    @property
    def refresh_token(self) -> str:
        return get_encryptor().decrypt(self._refresh_token) if self._refresh_token else ""

    @refresh_token.setter
    def refresh_token(self, val: str):
        if val:
            self._refresh_token = get_encryptor().encrypt(val)
        else:
            self._refresh_token = None

class EmailMetadata(Base):
    __tablename__ = "email_metadata"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    email_id = Column(String, nullable=False, index=True)  # API/IMAP unique ID
    thread_id = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    sender = Column(String, nullable=True)
    recipients = Column(Text, nullable=True)  # Comma-separated recipients
    timestamp = Column(DateTime, nullable=False, index=True)
    importance_score = Column(Float, default=0.0)
    synced_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="emails")

class SyncLog(Base):
    __tablename__ = "sync_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    status = Column(String, nullable=False)  # 'running', 'completed', 'failed'
    emails_synced = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text, nullable=True)

# Database Engine Init
DATABASE_URL = os.getenv("DATABASE_URL") or os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    cache_dir = Path(__file__).resolve().parents[2] / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    db_path = cache_dir / "email_intelligence.db"
    DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
