import httpx
import logging
import base64
import email.utils
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger("certificate_intelligence.email_sync_helpers")

def calculate_importance(text: str) -> float:
    keywords = {
        "certificate": 0.4, "credential": 0.4, "publication": 0.5, "published": 0.4, 
        "completion": 0.3, "completed": 0.3, "completing": 0.3, "course": 0.3, 
        "workshop": 0.2, "congratulations": 0.3, "congratulate": 0.3, "verified": 0.2, 
        "important": 0.2, "hackathon": 0.3, "achieved": 0.3
    }
    return min(round(0.1 + sum(val for kw, val in keywords.items() if kw in text.lower()), 2), 1.0)

async def fetch_gmail_emails(token: str) -> List[Dict[str, Any]]:
    emails, headers = [], {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        q = "certificate OR completion OR completed OR completing OR credential OR course OR training OR workshop OR hackathon OR publication OR bootcamp OR congratulations OR verified"
        res = await client.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q={q}&maxResults=200", headers=headers)
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
                        body += base64.urlsafe_b64decode(b_data.encode()).decode("utf-8", errors="ignore") + "\n"
                    except: pass
            emails.append({"id": msg["id"], "thread_id": detail.get("threadId"), "subject": sub, "sender": snd, "recipients": rec, "timestamp": ts, "body": body if body.strip() else detail.get("snippet", "")})
    return emails
