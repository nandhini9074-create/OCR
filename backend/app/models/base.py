import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
