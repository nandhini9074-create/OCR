import logging
import re
from typing import List, Dict, Any, Optional
from app.schemas.models import CertificateData, EmailIntelligence
from app.core.email_keywords import build_dynamic_keywords
from app.models.database import SessionLocal, EmailMetadata
from sqlalchemy import text

logger = logging.getLogger("certificate_intelligence.pipeline_email")

async def process_email_linkage(
    email: Optional[str], file_path_name: str, raw_ocr_text: str, cert_data: CertificateData,
    search_results: List[Dict[str, Any]], email_parser, matcher
) -> tuple[EmailIntelligence, Optional[Dict[str, Any]], float]:
    intel, parsed, conf = EmailIntelligence(matched_email=False), None, 0.0
    
    if not email:
        logger.warning("No recipient email filter provided. Bypassing database lookup.")
        intel.warning_message = "No email filter provided to scope database matching."
        return intel, parsed, conf

    db = SessionLocal()
    try:
        logger.info(f"Querying PostgreSQL database using Full-Text Search for tenant '{email}'...")
        
        # 1. Build search keywords
        kws = build_dynamic_keywords(cert_data, file_path_name)
        
        # 2. Format search query for PostgreSQL tsquery (OR-connected terms for broad matching and ranking)
        clean_kws = [re.sub(r'[^\w]', '', kw) for kw in kws if kw.strip()]
        clean_kws = [kw for kw in clean_kws if kw]
        
        query_str = " | ".join(clean_kws) if clean_kws else "certificate"
        logger.info(f"Generated Postgres FTS Query: '{query_str}'")
        
        # 3. Execute Indexed GIN Full-Text Query
        results = db.query(EmailMetadata)\
            .filter(EmailMetadata.user_id == email)\
            .filter(text("search_vector @@ to_tsquery('english', :query)"))\
            .params(query=query_str)\
            .order_by(text("ts_rank(search_vector, to_tsquery('english', :query)) DESC"))\
            .params(query=query_str)\
            .limit(10)\
            .all()
            
        logger.info(f"PostgreSQL FTS returned {len(results)} candidate email records.")
        
        # 4. Map SQL models to generic dictionaries for downstream LLM pipeline
        combined = [{
            "id": r.email_id,
            "subject": r.subject or "No Subject",
            "sender": r.sender or "Unknown",
            "date": str(r.timestamp),
            "body": r.body or ""
        } for r in results]
        
        if combined:
            # 5. Choose winning candidate via LLM Matcher
            matched, conf = await matcher.find_best_email_match(
                cert=cert_data, emails=combined, user_email=email, search_results=search_results
            )
            
            if matched:
                # 6. Parse and abstract winning details
                parsed = await email_parser.parse_email_content(matched)
                intel = EmailIntelligence(
                    matched_email=True, email_subject=matched.get("subject", "N/A"),
                    email_sender=matched.get("sender", "N/A"), email_date=str(matched.get("date", "N/A")),
                    email_body=matched.get("body", "N/A"), extracted_event_details=parsed.get("description", "N/A")
                )
                logger.info(f"Email matched SUCCESS: '{intel.email_subject}'")
            else:
                intel.warning_message = "Found matching database records, but engine determined none correspond to this certificate."
        else:
            intel.warning_message = "Successfully searched database index, but 0 matching emails were found for this tenant."
            
    except Exception as e:
        logger.error(f"Error in email matching pipeline: {e}", exc_info=True)
        intel.warning_message = f"Database FTS search failed: {str(e)}"
    finally:
        db.close()
        
    return intel, parsed, conf
