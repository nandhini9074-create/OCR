import imaplib, email, logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.core.matcher_heuristic import jaccard_similarity
from app.core.email_mime_utils import decode_mime_words, extract_body_text, extract_attachments

logger = logging.getLogger("certificate_intelligence.email_imap_client")

def fetch_emails_imap(login_user: str, oauth_rec, password: Optional[str], host: str, port: int, dynamic_kws: List[str], months_back: int, fname: Optional[str]) -> List[Dict[str, Any]]:
    fetched, mail = [], None
    try:
        mail = imaplib.IMAP4_SSL(host, port)
        if oauth_rec and oauth_rec.access_token:
            auth_string = f"user={login_user}\x01auth=Bearer {oauth_rec.access_token}\x01\x01".encode('utf-8')
            mail.authenticate('XOAUTH2', lambda x: auth_string)
        else: mail.login(login_user, password)
        mail.select("INBOX")
        since = (datetime.now() - timedelta(days=30 * months_back)).strftime("%d-%b-%Y")
        status, data = mail.search(None, f'(SINCE "{since}")')
        if status == "OK" and data[0]:
            matching_ids = set()
            for msg_id in reversed(data[0].split()[-150:]):
                h_status, h_data = mail.fetch(msg_id, "(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
                if h_status != "OK" or not h_data or not h_data[0]: continue
                h_msg = email.message_from_bytes(h_data[0][1])
                if any(kw in decode_mime_words(h_msg.get("Subject", "")).lower() or kw in decode_mime_words(h_msg.get("From", "")).lower() for kw in dynamic_kws): matching_ids.add(msg_id)
            for msg_id in matching_ids:
                b_status, b_data = mail.fetch(msg_id, "(RFC822)")
                if b_status == "OK" and b_data and b_data[0]:
                    raw_msg = email.message_from_bytes(b_data[0][1])
                    body, atts = extract_body_text(raw_msg), extract_attachments(raw_msg)
                    fetched.append({
                        "id": msg_id.decode(), "subject": decode_mime_words(raw_msg.get("Subject", "")), "sender": decode_mime_words(raw_msg.get("From", "")), "date": decode_mime_words(raw_msg.get("Date", "")),
                        "body": body, "attachments": atts, "has_matching_attachment": any(jaccard_similarity(fname.lower(), a.lower()) > 0.6 for a in atts) if fname else False
                    })
    except Exception as e: logger.error(f"IMAP lookup failed: {e}")
    finally:
        if mail:
            try: mail.close(); mail.logout()
            except Exception: pass
    return fetched
