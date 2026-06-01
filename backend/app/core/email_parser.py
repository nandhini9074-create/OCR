import os
import asyncio
import logging
from typing import Dict, Any
from app.utils.json_parser import parse_llm_json
from app.core.email_parser_helpers import build_email_parser_prompt

logger = logging.getLogger("certificate_intelligence.email_parser")

class EmailParser:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")

    async def parse_email_content(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asynchronously parse email text through the LLM to get structured event details.
        """
        if not email_data or not email_data.get("body", "").strip():
            logger.warning("Empty email data provided for parsing.")
            return {
                "event_name": "N/A", "issuer": "N/A", "recipient": "N/A", "date": "N/A", "description": "N/A"
            }

        prompt = build_email_parser_prompt(email_data)
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
            parsed_data = parse_llm_json(raw_result)
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
