import os, logging, asyncio
from typing import List, Dict, Any, Optional
from app.schemas.models import CertificateData, EventIntelligence
from app.utils.json_parser import parse_llm_json
from app.core.event_analyzer_prompt import build_event_analyzer_prompt

logger = logging.getLogger("certificate_intelligence.event_analyzer")

class EventAnalyzer:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        if not self.groq_key:
            logger.warning("Groq API key is not configured. 3-way synthesis will use baseline fallbacks.")

    async def analyze_event(
        self, cert_data: CertificateData, search_results: List[Dict[str, Any]], email_data: Optional[Dict[str, Any]] = None
    ) -> EventIntelligence:
        prompt = build_event_analyzer_prompt(cert_data, search_results, email_data)
        logger.info("Synthesizing 3-way event intelligence using Groq...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.groq_key, base_url="https://api.groq.com/openai/v1")
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(
                None, lambda: client.chat.completions.create(
                    model=self.groq_model, messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}, temperature=0.2
                )
            )
            parsed_data = parse_llm_json(res.choices[0].message.content)
            logger.info("Successfully synthesized 3-way merged Event Intelligence JSON.")
            return EventIntelligence(**parsed_data)
        except Exception as e:
            logger.error(f"Error in 3-way event intelligence synthesis: {e}. Falling back to baseline.")
            fallback_date = cert_data.date
            fallback_issuer = cert_data.issuer
            if email_data:
                fallback_date = email_data.get("date") or email_data.get("email_date") or cert_data.date
                fallback_issuer = email_data.get("issuer") or email_data.get("email_sender") or cert_data.issuer
            return EventIntelligence(
                purpose=f"Professional development and skill acquisition related to {cert_data.certificate_name}.",
                conducted_by=fallback_issuer, date=fallback_date, time="N/A", location="Online / Self-Paced",
                description=(
                    f"This represents a professional milestone where {cert_data.recipient} completed the {cert_data.certificate_name} "
                    f"credentials issued by {fallback_issuer} on {fallback_date}. This credential verifies knowledge and hands-on skills."
                )
            )
