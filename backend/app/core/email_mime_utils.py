import email, logging
from email.header import decode_header
from typing import List
from app.services.text_processor import get_text_processor

logger = logging.getLogger("certificate_intelligence.email_mime_utils")

def decode_mime_words(val: str) -> str:
    # Safeguard against empty headers to prevent program crashes
    if not val: return "N/A"
    try: 
        # email subjects/senders are often MIME encoded (e.g., =?UTF-8?Q?Hello?=). 
        # decode_header splits it into tuples (data, charset).
        # We loop through, decode bytes using their specific charset, and join them back into a clean string.
        return "".join([t.decode(c or 'utf-8', errors='ignore') if isinstance(t, bytes) else str(t) for t, c in decode_header(val)])
    # If decoding completely fails, return the raw string rather than crashing the app
    except Exception: return val

def extract_body_text(msg: email.message.Message) -> str:
    # Initialize empty string for body and load the HTML cleaner utility
    body, cleaner = "", get_text_processor().clean_html
    
    # msg.walk() iterates through all nested parts (text, html, attachments) of a multipart email
    for p in (msg.walk() if msg.is_multipart() else [msg]):
        
        # If the current part is an attachment (e.g., PDF), skip it. We only want body text here.
        if "attachment" in str(p.get("Content-Disposition")): continue
        
        ctype = p.get_content_type()
        
        # Prioritize plain text because it's the easiest and cleanest format for the LLM to read
        if ctype == "text/plain":
            try: 
                # Decode the base64/quoted-printable payload into raw bytes, then into a utf-8 string
                body += p.get_payload(decode=True).decode(p.get_content_charset() or 'utf-8', errors='ignore') + "\n"
            except Exception: pass
            
        # If there is no plain text, but HTML exists, use it as a fallback
        elif ctype == "text/html" and not body:
            try: 
                # Decode the HTML payload and pass it through our custom cleaner to strip <div>, <table>, etc.
                body += cleaner(p.get_payload(decode=True).decode(p.get_content_charset() or 'utf-8', errors='ignore')) + "\n"
            except Exception: pass
            
    # Return the clean text, removing any trailing or leading whitespace
    return body.strip()

def extract_attachments(msg: email.message.Message) -> List[str]:
    # One-liner list comprehension: Walks email parts -> checks if it's an attachment -> gets filename.
    # It decodes the filename (just like subjects) and returns a clean list of attachment names.
    return [decode_mime_words(p.get_filename()) for p in msg.walk() if msg.is_multipart() and "attachment" in str(p.get("Content-Disposition")) and p.get_filename()]
