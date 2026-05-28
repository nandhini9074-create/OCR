from typing import List, Dict, Any, Optional
from app.schemas.models import CertificateData

def build_event_analyzer_prompt(
    cert_data: CertificateData, search_results: List[Dict[str, Any]], email_data: Optional[Dict[str, Any]] = None
) -> str:
    search_context = "".join([
        f"Result {i}:\nTitle: {r.get('title')}\nSource: {r.get('url')}\nContent: {str(r.get('snippet') or r.get('content') or '')[:400]}\n\n"
        for i, r in enumerate(search_results[:3], 1)
    ]) if search_results else "No additional web search results are available."

    email_context = (
        f"- **Matched Subject**: {email_data.get('subject') or email_data.get('email_subject')}\n"
        f"- **Matched Sender**: {email_data.get('sender') or email_data.get('email_sender')}\n"
        f"- **Completion Date**: {email_data.get('date') or email_data.get('email_date')}\n"
        f"- **Email Snippet**: {(email_data.get('body') or email_data.get('email_body', ''))[:500]}"
    ) if email_data and email_data.get("matched_email", True) else "No relevant email was matched for this certificate."

    return f"""You are an expert Senior AI Systems Architect and Event Intelligence Specialist.
Your task is to synthesize information from three distinct sources (OCR certificate data, matching email communications, and supplementary web search context) to produce a single consolidated, highly accurate structured event intelligence JSON object.

### 1. Certificate Data (Extracted from Document OCR):
- **Certificate Name**: {cert_data.certificate_name}
- **Recipient**: {cert_data.recipient}
- **Issuer / Conducted By**: {cert_data.issuer}
- **Date**: {cert_data.date}
- **Skills Associated**: {", ".join(cert_data.skills) if cert_data.skills else "None explicitly listed"}

### 2. Matched Email Data (Extracted from Email Context):
{email_context}

### 3. Web Search Results (Event Enrichment):
{search_context}

### Synthesis and Conflict Resolution Rules:
1. **Remove Duplicates**: Eliminate duplicate or redundant entries and merge overlapping facts.
2. **Resolve Conflicts**: Priority 1: Email Data > Priority 2: OCR Certificate Data > Priority 3: Web Search Context.
3. **Data Specificity**:
   - `purpose`: Briefly explain the main educational or professional objective of the course/certificate.
   - `conducted_by`: Specify the exact organization, instructor, or institution.
   - `date`: Prefer specific completion date from the email or OCR certificate.
   - `time`: Estimate hours or specify course duration/time if found, otherwise 'N/A'.
   - `location`: Specify 'Online', 'In-Person', or 'Self-paced', including platform if known.
   - `description`: A clear, professional summary merging details from the certificate, emails, and web searches.

### Required Output Format:
Your output MUST be a strict, single JSON object conforming to the following structure:
{{
  "purpose": "Primary objective or goal of the certificate event",
  "conducted_by": "Organization/platform/speaker who conducted the event",
  "date": "Exact date or duration of the event (YYYY-MM-DD)",
  "time": "Time of the event or hours required, or N/A",
  "location": "Where the event was held",
  "description": "Concise, comprehensive description of the event"
}}"""
