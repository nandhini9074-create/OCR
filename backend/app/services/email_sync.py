import httpx, logging, asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.database import SessionLocal, OAuthToken, EmailMetadata, SyncLog, User
from app.auth.google import get_google_oauth
from app.services.text_processor import get_text_processor
from app.embeddings.embedder import get_embedder
from app.qdrant import get_qdrant_store

logger = logging.getLogger("certificate_intelligence.services.email_sync")

class EmailIngestService:
    def __init__(self):
        self.text_processor, self.embedder, self.qdrant = get_text_processor(), get_embedder(), get_qdrant_store()

    async def synchronize_user_inbox(self, user_id: str, provider: str) -> Dict[str, Any]:
        db: Session = SessionLocal()
        log_entry = SyncLog(user_id=user_id, provider=provider, status="running")
        db.add(log_entry)
        db.commit()
        try:
            if not db.query(User).filter(User.user_id == user_id).first():
                db.add(User(user_id=user_id))
                db.commit()

            token = db.query(OAuthToken).filter(OAuthToken.user_id == user_id, OAuthToken.provider == provider).first()
            if not token: raise ValueError(f"No OAuth credentials for user: {user_id} ({provider})")

            access_token = token.access_token
            if token.expires_at <= datetime.utcnow():
                logger.info(f"Access token expired. Refreshing OAuth...")
                res = await get_google_oauth().refresh_access_token(token.refresh_token)
                token.access_token = res["access_token"]
                token.expires_at = datetime.utcnow() + timedelta(seconds=res.get("expires_in", 3600))
                db.commit()
                access_token = token.access_token

            emails = await self._fetch_gmail_emails(access_token)
            logger.info(f"Fetched {len(emails)} emails from google.")

            new_emails = [m for m in emails if not db.query(EmailMetadata).filter(EmailMetadata.user_id == user_id, EmailMetadata.email_id == m["id"]).first()]
            logger.info(f"Found {len(new_emails)} new emails to index.")

            if not new_emails:
                log_entry.status, log_entry.emails_synced = "completed", 0
                db.commit()
                return {"status": "completed", "synced": 0}

            all_chunks = []
            for m in new_emails:
                clean_body = self.text_processor.remove_signature(self.text_processor.clean_html(m["body"]))
                chunks = self.text_processor.chunk_text(clean_body)
                importance = self._calculate_importance(m["subject"] + " " + clean_body)
                db.add(EmailMetadata(
                    user_id=user_id, email_id=m["id"], thread_id=m.get("thread_id"), subject=m["subject"],
                    sender=m["sender"], recipients=m.get("recipients", ""), timestamp=m["timestamp"], importance_score=importance
                ))
                all_chunks.extend([{
                    "user_id": user_id, "email_id": m["id"], "subject": m["subject"], "sender": m["sender"],
                    "recipients": m.get("recipients", "").split(","), "timestamp": m["timestamp"].isoformat(),
                    "thread_id": m.get("thread_id", ""), "chunk_text": ch, "importance_score": importance
                } for ch in chunks])
            db.commit()

            if all_chunks:
                vectors = await self.embedder.get_embeddings_batch([ch["chunk_text"] for ch in all_chunks])
                for idx, vec in enumerate(vectors):
                    all_chunks[idx]["vector"] = vec
                if not await self.qdrant.upsert_email_chunks(all_chunks):
                    raise RuntimeError("Qdrant upload failed.")

            log_entry.status, log_entry.emails_synced = "completed", len(new_emails)
            db.commit()
            return {"status": "completed", "synced": len(new_emails)}
        except Exception as e:
            logger.error(f"Sync error: {e}", exc_info=True)
            log_entry.status, log_entry.error_message = "failed", str(e)
            db.commit()
            return {"status": "failed", "error": str(e)}
        finally:
            db.close()

    def _calculate_importance(self, text: str) -> float:
        keywords = {"certificate": 0.4, "credential": 0.4, "publication": 0.5, "published": 0.4, "completion": 0.3, "workshop": 0.2, "congratulations": 0.3, "congratulate": 0.3, "verified": 0.2, "important": 0.2, "hackathon": 0.3}
        return min(round(0.1 + sum(val for kw, val in keywords.items() if kw in text.lower()), 2), 1.0)

    async def _fetch_gmail_emails(self, token: str) -> List[Dict[str, Any]]:
        emails, headers = [], {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            res = await client.get("https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=20", headers=headers)
            res.raise_for_status()
            for msg in res.json().get("messages", []):
                m_res = await client.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg['id']}", headers=headers)
                if m_res.status_code != 200: continue
                detail = m_res.json()
                h_list = detail.get("payload", {}).get("headers", [])
                sub = next((h["value"] for h in h_list if h["name"].lower() == "subject"), "No Subject")
                snd = next((h["value"] for h in h_list if h["name"].lower() == "from"), "Unknown Sender")
                rec = next((h["value"] for h in h_list if h["name"].lower() == "to"), "")
                dt = next((h["value"] for h in h_list if h["name"].lower() == "date"), None)
                ts = datetime.utcnow()
                if dt:
                    try:
                        import email.utils
                        t = email.utils.parsedate_tz(dt)
                        if t: ts = datetime.fromtimestamp(email.utils.mktime_tz(t))
                    except: pass
                body, parts = "", [detail.get("payload", {})]
                while parts:
                    p = parts.pop()
                    if p.get("parts"): parts.extend(p["parts"])
                    b_data = p.get("body", {}).get("data")
                    if b_data:
                        try:
                            import base64
                            body += base64.urlsafe_b64decode(b_data.encode()).decode("utf-8", errors="ignore") + "\n"
                        except: pass
                emails.append({"id": msg["id"], "thread_id": detail.get("threadId"), "subject": sub, "sender": snd, "recipients": rec, "timestamp": ts, "body": body if body.strip() else detail.get("snippet", "")})
        return emails

_sync_instance = None

def get_email_sync_service() -> EmailIngestService:
    global _sync_instance
    if _sync_instance is None: _sync_instance = EmailIngestService()
    return _sync_instance
