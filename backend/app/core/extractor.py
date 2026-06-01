import os
import asyncio
import logging
from app.schemas.models import CertificateData
from app.utils.json_parser import parse_llm_json
from app.core.extractor_helpers import build_extractor_prompt

logger = logging.getLogger("certificate_intelligence.extractor")

class CertificateExtractor:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
        
        if not self.groq_key:
            logger.warning("Groq API key is not configured. Extraction might fail.")

        logger.info(f"Initialized CertificateExtractor with Groq model: {self.groq_model}")

    async def extract_certificate_data(self, raw_ocr_text: str) -> CertificateData:
        """
        Asynchronously process raw OCR text through the LLM to get structured CertificateData.
        """
        if not raw_ocr_text or not raw_ocr_text.strip():
            logger.warning("Empty OCR text provided for extraction. Returning default empty model.")
            return CertificateData(
                certificate_name="Unknown Certificate", recipient="Unknown Recipient",
                issuer="Unknown Issuer", date="N/A", skills=[], confidence_score=0.0
            )

        prompt = build_extractor_prompt(raw_ocr_text)
        logger.info("Extracting certificate data using Groq...")

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
            logger.info("Successfully parsed structured LLM extraction.")
            return CertificateData(**parsed_data)

        except Exception as e:
            logger.error(f"Error in certificate data extraction: {e}")
            return CertificateData(
                certificate_name="Extraction Failed", recipient="Error",
                issuer="Error", date="N/A", skills=[], confidence_score=0.1
            )
