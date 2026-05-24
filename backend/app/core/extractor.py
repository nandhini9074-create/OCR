import os
import json
import asyncio
import re
import logging
from typing import Dict, Any, Optional
from app.schemas.models import CertificateData

logger = logging.getLogger("certificate_intelligence.extractor")

class CertificateExtractor:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
        
        if not self.groq_key:
            logger.warning("Groq API key is not configured. Extraction might fail.")

        logger.info(f"Initialized CertificateExtractor with Groq model: {self.groq_model}")

    def _clean_json_string(self, text: str) -> str:
        """Strip markdown code block wrappers (e.g. ```json ... ```) to extract a clean JSON string."""
        text = text.strip()
        # Regex to strip ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    def _parse_llm_json(self, raw_response: str) -> Dict[str, Any]:
        """Defensively parse JSON from LLM response, with fallback handling."""
        cleaned_text = self._clean_json_string(raw_response)
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error: {e}. Raw response was: {raw_response}")
            # Fallback regex extraction for a last-resort recovery
            try:
                # Attempt to find the first '{' and last '}'
                start_idx = cleaned_text.find("{")
                end_idx = cleaned_text.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    json_str = cleaned_text[start_idx:end_idx + 1]
                    return json.loads(json_str)
            except Exception as inner_e:
                logger.error(f"Fallback JSON extraction failed: {inner_e}")
            raise ValueError(f"Failed to parse a valid JSON structure from LLM response.")

    def _build_prompt(self, raw_ocr_text: str) -> str:
        """Create a highly descriptive prompt for structured metadata extraction."""
        return f"""
You are an advanced AI document understanding agent specializing in academic and professional certificates.
Analyze the following raw OCR text extracted from a certificate image or PDF.
Extract and structure the metadata into a single, clean JSON object matching the schema below.

### Raw OCR Text:
---
{raw_ocr_text}
---

### Extraction Rules:
1. **certificate_name**: Extract the official name of the certificate, course, or certification. Make it concise and professional.
2. **recipient**: Extract the full name of the person receiving the certificate.
3. **issuer**: Extract the organization, school, university, or platform that issued the certificate.
4. **date**: Extract the date the certificate was issued. Standardize it to "YYYY-MM-DD" format. If the exact day is missing, use "YYYY-MM-01" or similar. If no date is found, use "N/A".
5. **skills**: Analyze the certificate text and extract a list of skills, topics, tools, technologies, or concepts explicitly covered or strongly associated with this certification (e.g. ["Python", "FastAPI", "Machine Learning"]). If none are found, return an empty list [].
6. **confidence_score**: Provide a float value between 0.0 and 1.0 estimating your confidence in this extraction, based on the cleanliness and completeness of the OCR text.

### Required Output Format:
Your output MUST be a strict, single JSON object in this exact format, with no conversational preamble or postscript:
{{
  "certificate_name": "...",
  "recipient": "...",
  "issuer": "...",
  "date": "...",
  "skills": ["...", "..."],
  "confidence_score": 0.95
}}
"""

    async def extract_certificate_data(self, raw_ocr_text: str) -> CertificateData:
        """
        Asynchronously process raw OCR text through the LLM to get structured CertificateData.
        """
        if not raw_ocr_text or not raw_ocr_text.strip():
            logger.warning("Empty OCR text provided for extraction. Returning default empty model.")
            return CertificateData(
                certificate_name="Unknown Certificate",
                recipient="Unknown Recipient",
                issuer="Unknown Issuer",
                date="N/A",
                skills=[],
                confidence_score=0.0
            )

        prompt = self._build_prompt(raw_ocr_text)
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

            # Parse and validate the response
            parsed_data = self._parse_llm_json(raw_result)
            logger.info("Successfully parsed structured LLM extraction.")
            
            # Convert to Pydantic schema
            return CertificateData(**parsed_data)

        except Exception as e:
            logger.error(f"Error in certificate data extraction: {e}")
            # Return a graceful fallback instead of crashing the pipeline
            return CertificateData(
                certificate_name="Extraction Failed",
                recipient="Error",
                issuer="Error",
                date="N/A",
                skills=[],
                confidence_score=0.1
            )
