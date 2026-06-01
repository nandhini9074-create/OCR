import os
from datetime import datetime
import logging
from typing import Dict, Any
from app.auth.google_client import exchange_live_tokens, refresh_live_token

logger = logging.getLogger("certificate_intelligence.auth.google")

class GoogleOAuth:
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8001/auth/google/callback")
        
        self.is_mock = not self.client_id or not self.client_secret
        if self.is_mock:
            logger.warning("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET not configured. Google OAuth will run in DEV MOCK MODE.")

    def get_authorization_url(self, user_id: str) -> str:
        """Generate the Google authorization URL to redirect users to."""
        if self.is_mock:
            return f"http://localhost:8001/auth/google/callback?code=mock_google_code_for_{user_id}&state={user_id}"
            
        params = {
            "client_id": self.client_id, "redirect_uri": self.redirect_uri, "response_type": "code",
            "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/userinfo.email",
            "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true",
            "state": user_id, "login_hint": user_id
        }
        url = "https://accounts.google.com/o/oauth2/v2/auth"
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{url}?{query_string}"

    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange the Google Authorization Code for Access & Refresh Tokens."""
        if self.is_mock or code.startswith("mock_"):
            user_id = code.replace("mock_google_code_for_", "")
            return {
                "access_token": f"mock_google_access_token_for_{user_id}",
                "refresh_token": f"mock_google_refresh_token_for_{user_id}",
                "expires_in": 3600, "email": f"{user_id}@gmail.com"
            }
        return await exchange_live_tokens(code, self.client_id, self.client_secret, self.redirect_uri)

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Fetch a fresh Google Access Token using the stored Refresh Token."""
        if self.is_mock or refresh_token.startswith("mock_"):
            return {
                "access_token": f"mock_google_access_token_refreshed_{datetime.utcnow().timestamp()}",
                "expires_in": 3600
            }
        return await refresh_live_token(refresh_token, self.client_id, self.client_secret)

_google_oauth_instance = None

def get_google_oauth() -> GoogleOAuth:
    global _google_oauth_instance
    if _google_oauth_instance is None: _google_oauth_instance = GoogleOAuth()
    return _google_oauth_instance
