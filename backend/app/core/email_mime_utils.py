import email, logging
from email.header import decode_header
from typing import List
from app.services.text_processor import get_text_processor

logger = logging.getLogger("certificate_intelligence.email_mime_utils")

def decode_mime_words(val: str) -> str:
    if not val: return "N/A"
    try: return "".join([t.decode(c or 'utf-8', errors='ignore') if isinstance(t, bytes) else str(t) for t, c in decode_header(val)])
    except Exception: return val

def extract_body_text(msg: email.message.Message) -> str:
    body, cleaner = "", get_text_processor().clean_html
    for p in (msg.walk() if msg.is_multipart() else [msg]):
        if "attachment" in str(p.get("Content-Disposition")): continue
        ctype = p.get_content_type()
        if ctype == "text/plain":
            try: body += p.get_payload(decode=True).decode(p.get_content_charset() or 'utf-8', errors='ignore') + "\n"
            except Exception: pass
        elif ctype == "text/html" and not body:
            try: body += cleaner(p.get_payload(decode=True).decode(p.get_content_charset() or 'utf-8', errors='ignore')) + "\n"
            except Exception: pass
    return body.strip()

def extract_attachments(msg: email.message.Message) -> List[str]:
    return [decode_mime_words(p.get_filename()) for p in msg.walk() if msg.is_multipart() and "attachment" in str(p.get("Content-Disposition")) and p.get_filename()]
