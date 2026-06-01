import os, logging, asyncio
from typing import List, Dict, Any, Optional
from app.schemas.models import CertificateData, EventIntelligence
from app.utils.json_parser import parse_llm_json
from app.core.event_analyzer_prompt import build_event_analyzer_prompt
from app.core.extractor_rules import standardize_date, extract_issuer_spelling

logger = logging.getLogger("certificate_intelligence.event_analyzer")

class EventAnalyzer:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        
        self.is_offline = not self.groq_key
        if self.is_offline:
            logger.warning("Groq API key not configured. Event synthesis will run in purely deterministic offline mode.")

    def _run_deterministic_synthesis(self, cert_data: CertificateData, search_results: List[Dict[str, Any]], email_data: Optional[Dict[str, Any]] = None) -> EventIntelligence:
        """Deterministic 3-Way merging rules (No LLM required)."""
        # 1. Resolve exact date with priority: Email Header > OCR Certificate
        final_date = cert_data.date
        if email_data and email_data.get("email_date") and email_data.get("email_date") != "N/A":
            final_date = standardize_date(email_data["email_date"])
            
        # 2. Resolve clean issuer: Email Sender > OCR transcriptions
        final_issuer = cert_data.issuer
        if email_data and email_data.get("email_sender") and email_data.get("email_sender") != "N/A":
            final_issuer = extract_issuer_spelling(email_data["email_sender"])
            
        # 3. Pull details from web lookup if available
        web_desc = ""
        if search_results:
            web_desc = f" Verified by search metadata: {search_results[0].get('snippet', '')[:180]}..."
            
        desc = (
            f"Successfully verified milestone event where {cert_data.recipient} "
            f"completed the '{cert_data.certificate_name}' certification. The credential was "
            f"issued by {final_issuer} on {final_date}.{web_desc}"
        )
        return EventIntelligence(
            purpose=f"Professional development and skill acquisition in {', '.join(cert_data.skills[:3]) if cert_data.skills else 'specialized field'}.",
            conducted_by=final_issuer, date=final_date, time="N/A", location="Online / Self-Paced", description=desc
        )

    async def analyze_event(self, cert_data: CertificateData, search_results: List[Dict[str, Any]], email_data: Optional[Dict[str, Any]] = None) -> EventIntelligence:
        # Step 1: Programmatic Fallback for Standard Offline Users
        if self.is_offline:
            logger.info("Executing zero-cost programmatic 3-way event merge...")
            return self._run_deterministic_synthesis(cert_data, search_results, email_data)

        # Step 2: Live LLM Synthesis
        prompt = build_event_analyzer_prompt(cert_data, search_results, email_data)
        logger.info("Synthesizing 3-way event intelligence using Groq LLM...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.groq_key, base_url="https://api.groq.com/openai/v1")
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(
                None, lambda: client.chat.completions.create(model=self.groq_model, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.2)
            )
            parsed_data = parse_llm_json(res.choices[0].message.content)
            
            # Programmatic Output Post-Processing to guarantee clean date format
            parsed_data["date"] = standardize_date(parsed_data.get("date") or cert_data.date)
            parsed_data["conducted_by"] = extract_issuer_spelling(parsed_data.get("conducted_by") or cert_data.issuer)
            
            logger.info("Successfully completed 3-way event merge + output post-processing.")
            return EventIntelligence(**parsed_data)
        except Exception as e:
            logger.error(f"LLM event merge failed: {e}. Falling back to programmatic rules...")
            return self._run_deterministic_synthesis(cert_data, search_results, email_data)
