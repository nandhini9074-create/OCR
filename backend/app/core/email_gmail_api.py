import os, base64, logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.services.text_processor import get_text_processor
from app.core.matcher_heuristic import jaccard_similarity

logger = logging.getLogger("certificate_intelligence.email_gmail_api")

def fetch_emails_gmail_api(login_user: str, oauth_rec, dynamic_kws: List[str], months_back: int, fname: Optional[str]) -> List[Dict[str, Any]]:
    try:
        creds = Credentials(token=oauth_rec.access_token, refresh_token=oauth_rec.refresh_token, token_uri="https://oauth2.googleapis.com/token", client_id=os.getenv("GOOGLE_CLIENT_ID"), client_secret=os.getenv("GOOGLE_CLIENT_SECRET"), scopes=["https://www.googleapis.com/auth/gmail.readonly"])
        service = build('gmail', 'v1', credentials=creds)
        since = (datetime.now() - timedelta(days=30 * months_back)).strftime("%Y/%m/%d")
        t_kws = [kw for kw in dynamic_kws if len(kw) > 4][:5]
        q = f"after:{since} ({' OR '.join(t_kws)})" if t_kws else f"after:{since}"
        res_list = service.users().messages().list(userId='me', q=q, maxResults=15).execute().get('messages', [])
        emails, cleaner = [], get_text_processor().clean_html
        for msg_meta in res_list:
            msg = service.users().messages().get(userId='me', id=msg_meta['id'], format='full').execute()
            headers = {h['name'].lower(): h['value'] for h in msg['payload'].get('headers', [])}
            body, atts = "", []
            def walk_parts(part):
                nonlocal body
                mtype = part.get('mimeType', '')
                if part.get('filename'): atts.append(part.get('filename'))
                if 'parts' in part:
                    for p in part['parts']: walk_parts(p)
                else:
                    data = part.get('body', {}).get('data', '')
                    if data:
                        dec = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        if mtype == 'text/plain': body += dec + "\n"
                        elif mtype == 'text/html' and not body: body += cleaner(dec) + "\n"
            walk_parts(msg['payload'])
            emails.append({
                "id": msg_meta['id'], "subject": headers.get('subject', 'N/A'), "sender": headers.get('from', 'N/A'), "date": headers.get('date', 'N/A'),
                "body": body.strip(), "attachments": atts, "has_matching_attachment": any(jaccard_similarity(fname.lower(), a.lower()) > 0.6 for a in atts) if fname else False
            })
        return emails
    except Exception as e:
        logger.error(f"Gmail API lookup failed: {e}"); return []
