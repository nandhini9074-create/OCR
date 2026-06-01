import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.database import SessionLocal, OAuthToken, EmailMetadata, SyncLog, User
from app.auth.google import get_google_oauth
from app.services.text_processor import get_text_processor
from app.services.email_sync_helpers import calculate_importance, fetch_gmail_emails

logger = logging.getLogger("certificate_intelligence.services.email_sync")

class EmailIngestService:
    def __init__(self):
        self.text_processor = get_text_processor()

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

            emails = await fetch_gmail_emails(access_token)
            logger.info(f"Fetched {len(emails)} emails from google.")

            new_emails = [m for m in emails if not db.query(EmailMetadata).filter(EmailMetadata.user_id == user_id, EmailMetadata.email_id == m["id"]).first()]
            logger.info(f"Found {len(new_emails)} new emails to index.")

            if not new_emails:
                log_entry.status, log_entry.emails_synced = "completed", 0
                db.commit()
                return {"status": "completed", "synced": 0}

            synced_count = 0
            for m in new_emails:
                clean_body = self.text_processor.remove_signature(self.text_processor.clean_html(m["body"]))
                importance = calculate_importance(m["subject"] + " " + clean_body)
                if importance <= 0.1: continue
                db.add(EmailMetadata(
                    user_id=user_id, email_id=m["id"], thread_id=m.get("thread_id"), subject=m["subject"],
                    sender=m["sender"], recipients=m.get("recipients", ""), timestamp=m["timestamp"], 
                    importance_score=importance, body=clean_body
                ))
                synced_count += 1
            db.commit()

            cutoff_date = datetime.utcnow() - timedelta(days=365 * 2)
            deleted_rows = db.query(EmailMetadata).filter(
                EmailMetadata.user_id == user_id, EmailMetadata.timestamp < cutoff_date
            ).delete()
            if deleted_rows: logger.info(f"Purged {deleted_rows} historical emails older than 24 months for tenant '{user_id}'")
            db.commit()

            log_entry.status, log_entry.emails_synced = "completed", synced_count
            db.commit()
            return {"status": "completed", "synced": synced_count}
        except Exception as e:
            logger.error(f"Sync error: {e}", exc_info=True)
            log_entry.status, log_entry.error_message = "failed", str(e)
            db.commit()
            return {"status": "failed", "error": str(e)}
        finally:
            db.close()

_sync_instance = None

def get_email_sync_service() -> EmailIngestService:
    global _sync_instance
    if _sync_instance is None: _sync_instance = EmailIngestService()
    return _sync_instance
