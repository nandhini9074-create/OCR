import os, logging, asyncio
from typing import List, Dict, Any, Optional, Tuple
from app.schemas.models import CertificateData
from app.utils.json_parser import parse_llm_json
from app.core.matcher_heuristic import calculate_heuristic_score, jaccard_similarity
from app.core.matcher_prompt import build_matcher_prompt

logger = logging.getLogger("certificate_intelligence.matcher")

class CertificateEmailMatcher:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    async def find_best_email_match(
        self, cert: CertificateData, emails: List[Dict[str, Any]], user_email: Optional[str] = None, search_results: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        if not emails: return None, 0.0
        scored = sorted([(calculate_heuristic_score(cert, item, user_email), idx, item) for idx, item in enumerate(emails)], key=lambda x: x[0], reverse=True)
        logger.info("Heuristic matching scores:")
        for score, idx, item in scored[:5]:
            logger.info(f" - Index {idx} [Score: {score:.2f}]: '{item.get('subject')}'")
        if scored[0][0] <= 0.1:
            logger.info("Top heuristic score too low (<= 0.1). Skipping LLM verification.")
            return None, 0.0

        top_candidates = [item for _, _, item in scored[:4]]
        prompt = build_matcher_prompt(cert, top_candidates, user_email, search_results)
        logger.info("Triggering cognitive LLM matcher verification...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.groq_key, base_url="https://api.groq.com/openai/v1")
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(
                None, lambda: client.chat.completions.create(
                    model=self.groq_model, messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}, temperature=0.1
                )
            )
            parsed = parse_llm_json(res.choices[0].message.content)
            idx, conf = int(parsed.get("matched_index", -1)), float(parsed.get("matching_confidence", 0.0))
            if idx != -1 and idx < len(top_candidates):
                match_email = top_candidates[idx]
                logger.info(f"Cognitive Match SUCCESS [{conf:.2f}]: '{match_email.get('subject')}'")
                return match_email, conf
            return None, 0.0
        except Exception as e:
            logger.error(f"Error in cognitive LLM matcher: {e}")
            return (scored[0][2], 0.7) if scored[0][0] >= 4.0 else (None, 0.0)
