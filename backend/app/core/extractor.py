import os
import asyncio
import logging
from app.schemas.models import CertificateData
from app.utils.json_parser import parse_llm_json
from app.core.extractor_helpers import build_extractor_prompt
from app.core.extractor_rules import run_deterministic_extraction, standardize_date, extract_issuer_spelling, extract_skills_programmatic

logger = logging.getLogger("certificate_intelligence.extractor")

class CertificateExtractor:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
        
        self.is_offline = not self.groq_key
        if self.is_offline:
            logger.warning("Groq API key is not configured. Running in purely offline programmatic extractor mode.")

    async def extract_certificate_data(self, raw_ocr_text: str) -> CertificateData:
        """Asynchronously extract and structure CertificateData using hybrid LLM/programmatic rules."""
        if not raw_ocr_text or not raw_ocr_text.strip():
            return CertificateData(certificate_name="Unknown Certificate", recipient="Unknown Recipient", issuer="Unknown Issuer", date="N/A", skills=[], confidence_score=0.0)

        # Step 1: Programmatic Extractor Fallback for Standard Offline Users
        if self.is_offline:
            logger.info("Executing zero-cost programmatic rule-based extractor...")
            offline_data = run_deterministic_extraction(raw_ocr_text)
            return CertificateData(**offline_data)

        # Step 2: Live LLM Extraction
        prompt = build_extractor_prompt(raw_ocr_text)
        logger.info("Extracting certificate data using Groq LLM...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.groq_key, base_url="https://api.groq.com/openai/v1")
            
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, lambda: client.chat.completions.create(model=self.groq_model, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.1)
            )
            
            parsed_data = parse_llm_json(response.choices[0].message.content)
            
            # Step 3: Output Quality Programmatic Post-Processing
            parsed_data["date"] = standardize_date(parsed_data.get("date") or raw_ocr_text)
            parsed_data["issuer"] = extract_issuer_spelling(parsed_data.get("issuer") or raw_ocr_text)
            parsed_data["skills"] = list(set(parsed_data.get("skills", []) + extract_skills_programmatic(raw_ocr_text)))
            
            logger.info("Successfully completed LLM extraction + programmatic output quality post-processing.")
            return CertificateData(**parsed_data)

        except Exception as e:
            logger.error(f"Groq LLM extraction failed: {e}. Falling back to programmatic rules...")
            offline_data = run_deterministic_extraction(raw_ocr_text)
            return CertificateData(**offline_data)
