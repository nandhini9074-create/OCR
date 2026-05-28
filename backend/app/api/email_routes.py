from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.models.database import get_db, OAuthToken, User, SyncLog, EmailMetadata
from app.auth.google import get_google_oauth
from app.services.email_sync import get_email_sync_service
from app.rag.rag_engine import get_rag_engine
from app.qdrant.qdrant_client import get_qdrant_store
from app.embeddings.embedder import get_embedder

router = APIRouter()

# Used to enforce the input schema for vector search API requests
class SearchQuery(BaseModel):
    user_id: str
    query: str
    limit: Optional[int] = 5

# Used to enforce the input schema for generative RAG API requests
class RAGQuery(BaseModel):
    user_id: str
    query: str
    limit: Optional[int] = 5

# Used to securely save or update the OAuth tokens in the PostgreSQL database after successful login
def _save_oauth_token(user_id: str, provider: str, tokens: dict, db: Session):
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

# Used to start the Google OAuth flow by redirecting the user to the Google login screen
@router.get("/auth/google/login", summary="Initiate Google OAuth Flow")
async def google_login(user_id: str = Query(..., description="Unique ID of the user requesting authorization")):
    return {"redirect_url": get_google_oauth().get_authorization_url(user_id)}

# Used to receive the temporary authorization code from Google and exchange it for permanent access tokens
@router.get("/auth/google/callback", summary="Google Callback Endpoint")
async def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    try:
        tokens = await get_google_oauth().exchange_code_for_tokens(code)
        _save_oauth_token(state, "google", tokens, db)
        return RedirectResponse(url="http://localhost:5173/oauth-success.html?provider=google")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth login callback failed: {str(e)}")

# Used to tell the server to start downloading and vectorizing emails in the background without freezing the UI
@router.get("/emails/sync", summary="Trigger Asynchronous Email Indexing Sync")
async def trigger_inbox_sync(user_id: str, provider: str, background_tasks: BackgroundTasks):
    if provider != "google":
        raise HTTPException(status_code=400, detail="Invalid provider. Choose 'google'.")
    background_tasks.add_task(get_email_sync_service().synchronize_user_inbox, user_id, provider)
    return {"status": "syncing", "message": "Synchronizing inbox via google in the background. Check /emails/status for updates."}

# Used by the frontend to poll the database and check how many emails have been downloaded so far
@router.get("/emails/status", summary="Check Ingestion Progress Logs")
async def get_sync_status(user_id: str, db: Session = Depends(get_db)):
    logs = db.query(SyncLog).filter(SyncLog.user_id == user_id).order_by(SyncLog.timestamp.desc()).all()
    connections = {tok.provider: {"email": tok.email, "connected_at": tok.updated_at.isoformat()} for tok in db.query(OAuthToken).filter(OAuthToken.user_id == user_id).all()}
    email_count = db.query(EmailMetadata).filter(EmailMetadata.user_id == user_id).count()
    return {
        "user_id": user_id, "email_count": email_count, "connections": connections,
        "sync_history": [{"id": l.id, "provider": l.provider, "status": l.status, "emails_synced": l.emails_synced, "timestamp": l.timestamp.isoformat(), "error_message": l.error_message} for l in logs]
    }

# Used to let users search their own emails using AI Meaning (Semantics) instead of just keywords
@router.post("/search", summary="Vector Semantic Similarity Search")
async def semantic_search(query: SearchQuery):
    vec = await get_embedder().get_embedding(query.query)
    if not vec: raise HTTPException(status_code=500, detail="Failed to calculate query vector embedding.")
    hits = await get_qdrant_store().search_semantic(user_id=query.user_id, query_vector=vec, limit=query.limit)
    return {
        "query": query.query,
        "matches": [{
            "email_id": h["email_id"], "subject": h["subject"], "sender": h["sender"], "snippet": h["chunk_text"],
            "score": round(h["score"], 2), "timestamp": h["timestamp"], "thread_id": h.get("thread_id")
        } for h in hits]
    }

# Used to ask a conversational AI a question about your emails (e.g. 'When did I finish Python Bootcamp?')
@router.post("/rag/query", summary="RAG Conversation Q&A Synthesizer")
async def rag_query(query: RAGQuery):
    try:
        return await get_rag_engine().execute_rag_query(user_id=query.user_id, query=query.query, limit=query.limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query execution failed: {str(e)}")

# Used to completely wipe a user's data from PostgreSQL and Qdrant to comply with privacy laws (GDPR)
@router.delete("/emails/delete", summary="GDPR Wiping & Data Revocation")
async def delete_user_emails(user_id: str, db: Session = Depends(get_db)):
    try:
        db.query(EmailMetadata).filter(EmailMetadata.user_id == user_id).delete()
        db.query(OAuthToken).filter(OAuthToken.user_id == user_id).delete()
        db.query(SyncLog).filter(SyncLog.user_id == user_id).delete()
        db.commit()
        await get_qdrant_store().delete_user_vectors(user_id)
        return {"status": "deleted", "message": f"Successfully wiped all database metadata, OAuth records, and vector embeddings for user: '{user_id}'"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Revocation wipe failed: {str(e)}")
