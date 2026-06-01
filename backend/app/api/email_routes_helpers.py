from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from app.models.database import User, OAuthToken

class SearchQuery(BaseModel):
    user_id: str
    query: str
    limit: Optional[int] = 5

class RAGQuery(BaseModel):
    user_id: str
    query: str
    limit: Optional[int] = 5

def save_oauth_token(user_id: str, provider: str, tokens: dict, db: Session):
    if not db.query(User).filter(User.user_id == user_id).first():
        db.add(User(user_id=user_id))
    token_record = db.query(OAuthToken).filter(OAuthToken.user_id == user_id, OAuthToken.provider == provider).first()
    expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
    if not token_record:
        token_record = OAuthToken(user_id=user_id, provider=provider, email=tokens["email"], access_token=tokens["access_token"], refresh_token=tokens.get("refresh_token", ""), expires_at=expires_at)
        db.add(token_record)
    else:
        token_record.email, token_record.access_token, token_record.expires_at = tokens["email"], tokens["access_token"], expires_at
        if tokens.get("refresh_token"): token_record.refresh_token = tokens["refresh_token"]
    db.commit()
