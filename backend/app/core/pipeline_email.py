import logging
from typing import List, Dict, Any, Optional
from app.schemas.models import CertificateData, EmailIntelligence
from app.core.pipeline_qdrant import search_qdrant_emails

logger = logging.getLogger("certificate_intelligence.pipeline_email")

async def process_email_linkage(
    email: Optional[str], file_path_name: str, raw_ocr_text: str, cert_data: CertificateData,
    search_results: List[Dict[str, Any]], email_reader, email_parser, matcher
) -> tuple[EmailIntelligence, Optional[Dict[str, Any]], float]:
    intel, parsed, conf = EmailIntelligence(matched_email=False), None, 0.0
    try:
        logger.info("Accessing email inbox to search for matching certificate receipts...")
        recent = await email_reader.fetch_recent_emails(
            months_back=12, cert_data=cert_data, filename=file_path_name, raw_ocr_text=raw_ocr_text, user_email=email
        ) if email else []
        combined = list(recent)
        existing = {m["id"] for m in combined}
        for qe in await search_qdrant_emails(cert_data, email):
            if qe["id"] not in existing:
                combined.append(qe); existing.add(qe["id"])
        if combined:
            matched, conf = await matcher.find_best_email_match(cert=cert_data, emails=combined, user_email=email, search_results=search_results)
            if matched:
                parsed = await email_parser.parse_email_content(matched)
                intel = EmailIntelligence(
                    matched_email=True, email_subject=matched.get("subject", "N/A"),
                    email_sender=matched.get("sender", "N/A"), email_date=str(matched.get("date", "N/A")),
                    email_body=matched.get("body", "N/A"), extracted_event_details=parsed.get("description", "N/A")
                )
                logger.info(f"Email matched SUCCESS: '{intel.email_subject}'")
            else: intel.warning_message = "Found potential emails, but matching engine determined none correspond."
        else: intel.warning_message = "Successfully searched inbox, but 0 matching emails were found."
    except ValueError as ve:
        logger.warning(f"Email matching bypassed: {ve}"); intel.warning_message = str(ve)
    except Exception as e:
        logger.error(f"Error in email ingestion: {e}"); intel.warning_message = f"Email search failed: {str(e)}"
    return intel, parsed, conf
