import os, logging, asyncio
from typing import List, Dict, Any, Optional
from app.core.email_keywords import build_dynamic_keywords
from app.core.email_gmail_api import fetch_emails_gmail_api
from app.core.email_imap_client import fetch_emails_imap

logger = logging.getLogger("certificate_intelligence.email_reader")

class EmailReader:
    def __init__(self):
        # Fetch default IMAP settings from environment variables (fallback to Gmail's IMAP server)
        self.host, self.port = os.getenv("EMAIL_HOST", "imap.gmail.com"), int(os.getenv("EMAIL_PORT", "993"))
        # Fetch standard fallback email credentials (used if OAuth is not available)
        self.user = os.getenv("EMAIL_USER") or os.environ.get("EMAIL_USER")
        self.password = os.getenv("EMAIL_PASSWORD") or os.environ.get("EMAIL_PASSWORD")
        if not self.user or not self.password: logger.warning("Email credentials not configured.")

    def _fetch_emails_sync(self, months_back: int = 24, cert_data: Optional[Any] = None, filename: Optional[str] = None, raw_ocr_text: Optional[str] = None, user_email: Optional[str] = None) -> List[Dict[str, Any]]:
        # Determine the user to login as (either the provided user_email or the system default)
        login_user, oauth_rec = user_email or self.user, None
        
        if login_user:
            try:
                # Query the SQLite database to check if this user has authorized Google OAuth
                from app.models.database import SessionLocal, OAuthToken
                db = SessionLocal()
                oauth_rec = db.query(OAuthToken).filter((OAuthToken.email == login_user) | (OAuthToken.user_id == login_user)).first()
                db.close()
            except Exception as e: logger.error(f"OAuth token lookup failed: {e}")
            
        # If no OAuth token AND no fallback password exists, we cannot proceed securely
        if not oauth_rec and (not login_user or not self.password): raise ValueError("No active credentials or Google OAuth tokens found.")
        
        # Build smart, targeted search keywords from the certificate details and filename
        d_kws = build_dynamic_keywords(cert_data, filename)
        
        # ROUTING LOGIC: If we have a Google OAuth token, route the request to the blazing fast Gmail API
        if oauth_rec and getattr(oauth_rec, 'provider', None) == 'google': return fetch_emails_gmail_api(login_user, oauth_rec, d_kws, months_back, filename)
        
        # ROUTING LOGIC: If no Google token (or it's a different provider), fallback to standard IMAP
        return fetch_emails_imap(login_user, oauth_rec, self.password, self.host, self.port, d_kws, months_back, filename)

    async def fetch_recent_emails(self, months_back: int = 24, cert_data: Optional[Any] = None, filename: Optional[str] = None, raw_ocr_text: Optional[str] = None, user_email: Optional[str] = None) -> List[Dict[str, Any]]:
        try: 
            # The underlying email fetch functions are synchronous (blocking).
            # To prevent freezing the FastAPI server, we run them in a background thread executor using asyncio.
            return await asyncio.get_running_loop().run_in_executor(None, self._fetch_emails_sync, months_back, cert_data, filename, raw_ocr_text, user_email)
        except Exception as e: 
            logger.error(f"Async email fetch failed: {e}"); raise
