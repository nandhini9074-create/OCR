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
        # Create Google OAuth credentials using the saved tokens to authorize API access
        creds = Credentials(token=oauth_rec.access_token, refresh_token=oauth_rec.refresh_token, token_uri="https://oauth2.googleapis.com/token", client_id=os.getenv("GOOGLE_CLIENT_ID"), client_secret=os.getenv("GOOGLE_CLIENT_SECRET"), scopes=["https://www.googleapis.com/auth/gmail.readonly"])
        
        # Build the Gmail service client to interact with Google's servers
        service = build('gmail', 'v1', credentials=creds)
        
        # Calculate the cutoff date to restrict search to recent emails (performance optimization)
        since = (datetime.now() - timedelta(days=30 * months_back)).strftime("%Y/%m/%d")
        
        # Filter keywords to those > 4 chars and limit to top 5 to avoid API query limits
        t_kws = [kw for kw in dynamic_kws if len(kw) > 4][:5]
        
        # Construct the Gmail native search query (e.g., 'after:2024/01/01 (cert OR complete)')
        q = f"after:{since} ({' OR '.join(t_kws)})" if t_kws else f"after:{since}"
        
        # Execute the search query and fetch maximum 30 message IDs
        res_list = service.users().messages().list(userId='me', q=q, maxResults=30).execute().get('messages', [])
        
        # Initialize results list and get the HTML cleaner utility
        emails, cleaner = [], get_text_processor().clean_html
        
        for msg_meta in res_list:
            # Fetch the full payload (headers, body, attachments) for a specific email ID
            msg = service.users().messages().get(userId='me', id=msg_meta['id'], format='full').execute()
            
            # Extract essential headers into a dictionary for quick access
            headers = {h['name'].lower(): h['value'] for h in msg['payload'].get('headers', [])}
            body, atts = "", []
        
            
            # Recursive function to parse complex nested MIME structures in emails
            def walk_parts(part):
                nonlocal body
                mtype = part.get('mimeType', '')
                
                # If a filename exists, it's an attachment
                if part.get('filename'): atts.append(part.get('filename'))
                
                # If there are sub-parts (multipart), recurse deeper
                if 'parts' in part:
                    for p in part['parts']: walk_parts(p)
                else:
                    # It's a leaf node containing actual data
                    data = part.get('body', {}).get('data', '')
                    if data:
                        # Decode the URL-safe base64 data returned by Gmail
                        dec = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        
                        # Prioritize plain text; if only HTML exists, clean the tags before appending
                        if mtype == 'text/plain': body += dec + "\n"
                        elif mtype == 'text/html' and not body: body += cleaner(dec) + "\n"
                        
            # Start parsing from the root payload
            walk_parts(msg['payload'])
            
            # Package the extracted data and calculate attachment similarity score
            emails.append({
                "id": msg_meta['id'], "subject": headers.get('subject', 'N/A'), "sender": headers.get('from', 'N/A'), "date": headers.get('date', 'N/A'),
                "body": body.strip(), "attachments": atts, 
                # Check if any attachment name is highly similar to the uploaded cert filename (>60% match)
                "has_matching_attachment": any(jaccard_similarity(fname.lower(), a.lower()) > 0.6 for a in atts) if fname else False
            })
        return emails
    except Exception as e:
        # Prevent the entire pipeline from crashing if Gmail fetch fails
        logger.error(f"Gmail API lookup failed: {e}"); return []
