import logging
from typing import List, Dict, Any, Optional
from app.schemas.models import CertificateData, EmailIntelligence
from app.core.pipeline_qdrant import search_qdrant_emails

logger = logging.getLogger("certificate_intelligence.pipeline_email")

async def process_email_linkage(
    email: Optional[str], file_path_name: str, raw_ocr_text: str, cert_data: CertificateData,
    search_results: List[Dict[str, Any]], email_reader, email_parser, matcher
) -> tuple[EmailIntelligence, Optional[Dict[str, Any]], float]:
    
    # Set default fallback values in case no matching email is ever found
    intel, parsed, conf = EmailIntelligence(matched_email=False), None, 0.0
    
    try:
        logger.info("Accessing email inbox to search for matching certificate receipts...")
        
        # 1. LIVE SEARCH: Fetch recent emails using exact keywords via Gmail API or IMAP
        recent = await email_reader.fetch_recent_emails(
            months_back=24, cert_data=cert_data, filename=file_path_name, raw_ocr_text=raw_ocr_text, user_email=email
        ) if email else []
        
        combined = list(recent)
        
        # Keep track of existing email IDs to prevent adding duplicates in the next step
        existing = {m["id"] for m in combined}
        
        # 2. AI VECTOR SEARCH: Query the Qdrant DB using semantic meaning to find emails the live search missed
        for qe in await search_qdrant_emails(cert_data, email):
            if qe["id"] not in existing:
                combined.append(qe); existing.add(qe["id"])
                
        # If we found any potential emails (either from Live Search or AI Search)
        if combined:
            
            # 3. LLM MATCHING: Ask the AI to read all potential emails and pick the EXACT one that acts as a receipt
            matched, conf = await matcher.find_best_email_match(cert=cert_data, emails=combined, user_email=email, search_results=search_results)
            
            # If the AI successfully selected a matching email
            if matched:
                
                # 4. LLM PARSING: Ask the AI to summarize the winning email and extract event/course details
                parsed = await email_parser.parse_email_content(matched)
                
                # Package the final winning data into the EmailIntelligence output schema
                intel = EmailIntelligence(
                    matched_email=True, email_subject=matched.get("subject", "N/A"),
                    email_sender=matched.get("sender", "N/A"), email_date=str(matched.get("date", "N/A")),
                    email_body=matched.get("body", "N/A"), extracted_event_details=parsed.get("description", "N/A")
                )
                logger.info(f"Email matched SUCCESS: '{intel.email_subject}'")
                
            # The AI read the emails but decided none of them were actual receipts for this certificate
            else: intel.warning_message = "Found potential emails, but matching engine determined none correspond."
            
        # The keyword and vector searches both returned 0 results
        else: intel.warning_message = "Successfully searched inbox, but 0 matching emails were found."
        
    except ValueError as ve:
        # Gracefully handle known setup issues (like missing passwords/tokens) without crashing
        logger.warning(f"Email matching bypassed: {ve}"); intel.warning_message = str(ve)
    except Exception as e:
        # Catch any unexpected code crashes (e.g., network timeout) and convert them to frontend warnings
        logger.error(f"Error in email ingestion: {e}"); intel.warning_message = f"Email search failed: {str(e)}"
        
    # Return the packaged intelligence, parsed summary, and AI confidence score
    return intel, parsed, conf
