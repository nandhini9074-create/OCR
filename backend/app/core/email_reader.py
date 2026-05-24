import os, logging, asyncio
from typing import List, Dict, Any, Optional
from app.core.email_keywords import build_dynamic_keywords
from app.core.email_gmail_api import fetch_emails_gmail_api
from app.core.email_imap_client import fetch_emails_imap

logger = logging.getLogger("certificate_intelligence.email_reader")

class EmailReader:
    def __init__(self):
        self.host, self.port = os.getenv("EMAIL_HOST", "imap.gmail.com"), int(os.getenv("EMAIL_PORT", "993"))
        self.user = os.getenv("EMAIL_USER") or os.environ.get("EMAIL_USER")
        self.password = os.getenv("EMAIL_PASSWORD") or os.environ.get("EMAIL_PASSWORD")
        if not self.user or not self.password: logger.warning("Email credentials not configured.")

    def _fetch_emails_sync(self, months_back: int = 12, cert_data: Optional[Any] = None, filename: Optional[str] = None, raw_ocr_text: Optional[str] = None, user_email: Optional[str] = None) -> List[Dict[str, Any]]:
        login_user, oauth_rec = user_email or self.user, None
        if login_user:
            try:
                from app.models.database import SessionLocal, OAuthToken
                db = SessionLocal()
                oauth_rec = db.query(OAuthToken).filter((OAuthToken.email == login_user) | (OAuthToken.user_id == login_user)).first()
                db.close()
            except Exception as e: logger.error(f"OAuth token lookup failed: {e}")
        if not oauth_rec and (not login_user or not self.password): raise ValueError("No active credentials or Google OAuth tokens found.")
        d_kws = build_dynamic_keywords(cert_data, filename)
        if oauth_rec and getattr(oauth_rec, 'provider', None) == 'google': return fetch_emails_gmail_api(login_user, oauth_rec, d_kws, months_back, filename)
        return fetch_emails_imap(login_user, oauth_rec, self.password, self.host, self.port, d_kws, months_back, filename)

    async def fetch_recent_emails(self, months_back: int = 12, cert_data: Optional[Any] = None, filename: Optional[str] = None, raw_ocr_text: Optional[str] = None, user_email: Optional[str] = None) -> List[Dict[str, Any]]:
        try: return await asyncio.get_running_loop().run_in_executor(None, self._fetch_emails_sync, months_back, cert_data, filename, raw_ocr_text, user_email)
        except Exception as e: logger.error(f"Async email fetch failed: {e}"); raise
