import os
import json
import re
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger("certificate_intelligence.email_parser")

class EmailParser:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")

    def _clean_json_string(self, text: str) -> str:
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    def _parse_llm_json(self, raw_response: str) -> Dict[str, Any]:
        cleaned_text = self._clean_json_string(raw_response)
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error: {e}. Raw response: {raw_response}")
            try:
                start_idx = cleaned_text.find("{")
                end_idx = cleaned_text.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    json_str = cleaned_text[start_idx:end_idx + 1]
                    return json.loads(json_str)
            except Exception as inner_e:
                logger.error(f"Fallback JSON parsing failed: {inner_e}")
            raise ValueError(f"Could not parse valid JSON from LLM response.")

    def _build_prompt(self, email_data: Dict[str, Any]) -> str:
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

    async def parse_email_content(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asynchronously parse email text through the LLM to get structured event details.
        """
        if not email_data or not email_data.get("body", "").strip():
            logger.warning("Empty email data provided for parsing.")
            return {
                "event_name": "N/A",
                "issuer": "N/A",
                "recipient": "N/A",
                "date": "N/A",
                "description": "N/A"
            }

        prompt = self._build_prompt(email_data)
        logger.info("Structuring email event details using Groq...")

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.groq_key, base_url="https://api.groq.com/openai/v1")
            
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=self.groq_model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
            )
            
            raw_result = response.choices[0].message.content

            parsed_data = self._parse_llm_json(raw_result)
            logger.info("Successfully structured email event details.")
            return parsed_data

        except Exception as e:
            logger.error(f"Error parsing email details through LLM: {e}")
            return {
                "event_name": email_data.get("subject", "N/A"),
                "issuer": email_data.get("sender", "N/A"),
                "recipient": "N/A",
                "date": email_data.get("date", "N/A"),
                "description": f"Extracted from email: '{email_data.get('subject')}'. Body analysis failed: {str(e)}"
            }
