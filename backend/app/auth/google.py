import os
import httpx
from datetime import datetime, timedelta
import logging
from typing import Dict, Any

logger = logging.getLogger("certificate_intelligence.auth.google")

# Used to handle all secure communication and token management with Google's OAuth 2.0 servers
class GoogleOAuth:
    # Used to load the secret Google App Credentials required to prove the app's identity to Google
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8001/auth/google/callback")
        
        # Used to allow developers to test the app without needing a real Google Developer account setup
        self.is_mock = not self.client_id or not self.client_secret
        if self.is_mock:
            logger.warning("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET not configured. Google OAuth will run in DEV MOCK MODE.")

    # Used to generate the exact Google Login URL that the user clicks on the frontend to grant permission
    def get_authorization_url(self, user_id: str) -> str:
        if self.is_mock:
            return f"http://localhost:8001/auth/google/callback?code=mock_google_code_for_{user_id}&state={user_id}"
            
        # Used to strictly define what we can access (read-only emails, offline access for background syncing)
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/userinfo.email",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": user_id,
            "login_hint": user_id
        }
        url = "https://accounts.google.com/o/oauth2/v2/auth"
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{url}?{query_string}"

    # Used to securely trade the temporary code Google gives us for permanent Access and Refresh tokens
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        if self.is_mock or code.startswith("mock_"):
            user_id = code.replace("mock_google_code_for_", "")
            return {
                "access_token": f"mock_google_access_token_for_{user_id}",
                "refresh_token": f"mock_google_refresh_token_for_{user_id}",
                "expires_in": 3600,
                "email": f"{user_id}@gmail.com"
            }

        url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }
        
        async with httpx.AsyncClient() as client:
            res = await client.post(url, data=payload)
            res.raise_for_status()
            data = res.json()
            
            # Used to immediately figure out the user's real email address so we can save it in our Database
            email = await self._fetch_user_email(data.get("access_token"))
            data["email"] = email
            return data

    # Used to automatically get a fresh 1-hour Access Token using the saved Refresh Token, preventing forced re-logins
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        if self.is_mock or refresh_token.startswith("mock_"):
            return {
                "access_token": f"mock_google_access_token_refreshed_{datetime.utcnow().timestamp()}",
                "expires_in": 3600
            }

        url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        async with httpx.AsyncClient() as client:
            res = await client.post(url, data=payload)
            res.raise_for_status()
            return res.json()

    # Used to securely ask Google's Profile API for the logged-in user's exact email address
    async def _fetch_user_email(self, access_token: str) -> str:
        url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers)
                res.raise_for_status()
                return res.json().get("email", "unknown@gmail.com")
        except Exception as e:
            logger.error(f"Failed to fetch Google profile email: {e}")
            return "unknown@gmail.com"

_google_oauth_instance = None

# Used to enforce the Singleton pattern so we don't reload the .env variables every time a user logs in
def get_google_oauth() -> GoogleOAuth:
    global _google_oauth_instance
    if _google_oauth_instance is None:
        _google_oauth_instance = GoogleOAuth()
    return _google_oauth_instance
