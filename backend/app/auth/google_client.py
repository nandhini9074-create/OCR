import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger("certificate_intelligence.auth.google_client")

async def fetch_user_email(access_token: str) -> str:
    """Fetch the authenticated user's email address from Google Profile APIs."""
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

async def exchange_live_tokens(code: str, client_id: str, client_secret: str, redirect_uri: str) -> Dict[str, Any]:
    url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code, "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": redirect_uri, "grant_type": "authorization_code"
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(url, data=payload)
        res.raise_for_status()
        data = res.json()
        email = await fetch_user_email(data.get("access_token"))
        data["email"] = email
        return data

async def refresh_live_token(refresh_token: str, client_id: str, client_secret: str) -> Dict[str, Any]:
    url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token"
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(url, data=payload)
        res.raise_for_status()
        return res.json()
