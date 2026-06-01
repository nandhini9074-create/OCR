from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any

from app.models.database import get_db, OAuthToken, SyncLog, EmailMetadata
from app.auth.google import get_google_oauth
from app.services.email_sync import get_email_sync_service
from app.rag.rag_engine import get_rag_engine
from app.api.email_routes_helpers import SearchQuery, RAGQuery, save_oauth_token

router = APIRouter()

@router.get("/auth/google/login", summary="Initiate Google OAuth Flow")
async def google_login(user_id: str = Query(..., description="Unique ID of the user requesting authorization")):
    return {"redirect_url": get_google_oauth().get_authorization_url(user_id)}

@router.get("/auth/google/callback", summary="Google Callback Endpoint")
async def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    try:
        tokens = await get_google_oauth().exchange_code_for_tokens(code)
        save_oauth_token(state, "google", tokens, db)
        return RedirectResponse(url="http://localhost:5173/oauth-success.html?provider=google")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth login callback failed: {str(e)}")

@router.get("/emails/sync", summary="Trigger Asynchronous Email Indexing Sync")
async def trigger_inbox_sync(user_id: str, provider: str, background_tasks: BackgroundTasks):
    if provider != "google": raise HTTPException(status_code=400, detail="Invalid provider. Choose 'google'.")
    background_tasks.add_task(get_email_sync_service().synchronize_user_inbox, user_id, provider)
    return {"status": "syncing", "message": "Synchronizing inbox via google in the background. Check /emails/status for updates."}

@router.get("/emails/status", summary="Check Ingestion Progress Logs")
async def get_sync_status(user_id: str, db: Session = Depends(get_db)):
    logs = db.query(SyncLog).filter(SyncLog.user_id == user_id).order_by(SyncLog.timestamp.desc()).all()
    connections = {tok.provider: {"email": tok.email, "connected_at": tok.updated_at.isoformat()} for tok in db.query(OAuthToken).filter(OAuthToken.user_id == user_id).all()}
    email_count = db.query(EmailMetadata).filter(EmailMetadata.user_id == user_id).count()
    return {
        "user_id": user_id, "email_count": email_count, "connections": connections,
        "sync_history": [{"id": l.id, "provider": l.provider, "status": l.status, "emails_synced": l.emails_synced, "timestamp": l.timestamp.isoformat(), "error_message": l.error_message} for l in logs]
    }

@router.post("/search", summary="Vector Semantic Similarity Search")
async def semantic_search(query: SearchQuery, db: Session = Depends(get_db)):
    import re
    words = re.sub(r'[^\w\s]', '', query.query).split()
    query_str = " & ".join(w for w in words if w) if words else "certificate"
    try:
        results = db.query(EmailMetadata)\
            .filter(EmailMetadata.user_id == query.user_id)\
            .filter(text("search_vector @@ to_tsquery('english', :query)"))\
            .params(query=query_str)\
            .order_by(text("ts_rank(search_vector, to_tsquery('english', :query)) DESC"))\
            .params(query=query_str)\
            .limit(query.limit)\
            .all()
        return {
            "query": query.query,
            "matches": [{
                "email_id": r.email_id, "subject": r.subject or "No Subject", "sender": r.sender or "Unknown", 
                "snippet": r.body[:250] + "..." if r.body and len(r.body) > 250 else (r.body or ""),
                "score": 1.0, "timestamp": r.timestamp.isoformat() if r.timestamp else "", "thread_id": r.thread_id or "N/A"
            } for r in results]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database FTS search failed: {str(e)}")

@router.post("/rag/query", summary="RAG Conversation Q&A Synthesizer")
async def rag_query(query: RAGQuery):
    try:
        return await get_rag_engine().execute_rag_query(user_id=query.user_id, query=query.query, limit=query.limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query execution failed: {str(e)}")

@router.delete("/emails/delete", summary="GDPR Wiping & Data Revocation")
async def delete_user_emails(user_id: str, db: Session = Depends(get_db)):
    try:
        db.query(EmailMetadata).filter(EmailMetadata.user_id == user_id).delete()
        db.query(OAuthToken).filter(OAuthToken.user_id == user_id).delete()
        db.query(SyncLog).filter(SyncLog.user_id == user_id).delete()
        db.commit()
        return {"status": "deleted", "message": f"Successfully wiped all database metadata and OAuth records for user: '{user_id}'"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Revocation wipe failed: {str(e)}")
