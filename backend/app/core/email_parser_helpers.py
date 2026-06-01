from typing import Dict, Any

def build_email_parser_prompt(email_data: Dict[str, Any]) -> str:
    return f"""
You are an expert AI Data Extraction Agent specializing in professional and academic confirmation emails.
Your task is to analyze the following email metadata and body text, and extract structured event/certificate coordinates.

### Email Details:
- **From/Sender**: {email_data.get('sender')}
- **Subject Line**: {email_data.get('subject')}
- **Date Received**: {email_data.get('date')}
- **Body Content**:
---
{email_data.get('body')}
---

### Extraction Guidelines:
1. **event_name**: Extract the specific name of the course, training program, workshop, internship, hackathon, or certification referenced.
2. **issuer**: Extract the organization, school, university, company, or platform that conducted the event or issued the certificate.
3. **recipient**: Extract the full name of the recipient (the person to whom the email is addressed or who is confirmed).
4. **date**: Extract the date the event occurred, was completed, or the email date. Standardize it to YYYY-MM-DD format if possible.
5. **description**: Synthesize a concise 2-3 sentence description of the event details, schedule coordinates, or description extracted from the email.

### Required Output Format:
Your output MUST be a strict, single JSON object matching this exact format, with no conversational preamble or postscript:
{{
  "event_name": "...",
  "issuer": "...",
  "recipient": "...",
  "date": "...",
  "description": "..."
}}
"""
