import imaplib, email, logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.core.matcher_heuristic import jaccard_similarity
from app.core.email_mime_utils import decode_mime_words, extract_body_text, extract_attachments

logger = logging.getLogger("certificate_intelligence.email_imap_client")

def fetch_emails_imap(login_user: str, oauth_rec, password: Optional[str], host: str, port: int, dynamic_kws: List[str], months_back: int, fname: Optional[str]) -> List[Dict[str, Any]]:
    fetched, mail = [], None
    try:
        # Establish a secure SSL-encrypted connection to the IMAP email server (e.g., imap.gmail.com:993)
        mail = imaplib.IMAP4_SSL(host, port)
        
        if oauth_rec and oauth_rec.access_token:
            # If Google OAuth token is available, use the modern, highly secure XOAUTH2 authentication
            auth_string = f"user={login_user}\x01auth=Bearer {oauth_rec.access_token}\x01\x01".encode('utf-8')
            mail.authenticate('XOAUTH2', lambda x: auth_string)
        else: 
            # Fallback to traditional username/App-password login if OAuth is not available (e.g., for non-Google accounts)
            mail.login(login_user, password)
            
        # Select the main INBOX folder to limit the search scope
        mail.select("INBOX")
        
        # Calculate the cutoff date and format it specifically for IMAP (e.g., '01-Jan-2024')
        since = (datetime.now() - timedelta(days=30 * months_back)).strftime("%d-%b-%Y")
        
        # Ask the IMAP server for IDs of all emails received after the cutoff date
        status, data = mail.search(None, f'(SINCE "{since}")')
        
        if status == "OK" and data[0]:
            matching_ids = set()
            
            # Loop through the latest 500 emails, starting from the newest (reversed), to optimize performance
            for msg_id in reversed(data[0].split()[-500:]):
                
                # OPTIMIZATION: Fetch ONLY the essential headers (Subject, From, Date) instead of the whole email
                h_status, h_data = mail.fetch(msg_id, "(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
                if h_status != "OK" or not h_data or not h_data[0]: continue
                
                # Parse the raw header bytes into a standard Python email object
                h_msg = email.message_from_bytes(h_data[0][1])
                
                # Check if any dynamically generated keywords exist in the Subject or Sender fields (after decoding MIME text)
                if any(kw in decode_mime_words(h_msg.get("Subject", "")).lower() or kw in decode_mime_words(h_msg.get("From", "")).lower() for kw in dynamic_kws): 
                    # Use a set to store unique matching IDs
                    matching_ids.add(msg_id)
                    
            # Now, only process the emails that actually matched our keywords
            for msg_id in matching_ids:
                # Fetch the FULL email content (RFC822 is the IMAP standard for the complete raw message)
                b_status, b_data = mail.fetch(msg_id, "(RFC822)")
                if b_status == "OK" and b_data and b_data[0]:
                    
                    # Parse the full raw email bytes into a Python object
                    raw_msg = email.message_from_bytes(b_data[0][1])
                    
                    # Use custom helper functions to safely extract the plain/HTML body and attachment filenames
                    body, atts = extract_body_text(raw_msg), extract_attachments(raw_msg)
                    
                    # Package the fully extracted email data into a structured dictionary
                    fetched.append({
                        "id": msg_id.decode(), "subject": decode_mime_words(raw_msg.get("Subject", "")), "sender": decode_mime_words(raw_msg.get("From", "")), "date": decode_mime_words(raw_msg.get("Date", "")),
                        "body": body, "attachments": atts, 
                        # Check if any attachment name is highly similar to the uploaded cert filename (>60% match)
                        "has_matching_attachment": any(jaccard_similarity(fname.lower(), a.lower()) > 0.6 for a in atts) if fname else False
                    })
    except Exception as e: 
        # Log IMAP errors but don't crash the pipeline
        logger.error(f"IMAP lookup failed: {e}")
    finally:
        if mail:
            # Always close the INBOX and logout properly to prevent leaving ghost connections on the IMAP server
            try: mail.close(); mail.logout()
            except Exception: pass
    return fetched
