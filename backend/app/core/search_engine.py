import os, asyncio, logging, httpx
from typing import List, Dict, Any
logger = logging.getLogger("certificate_intelligence.search_engine")

class TavilySearchEngine:
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY") or os.environ.get("TAVILY_API_KEY")
        self.api_url = "https://api.tavily.com/search"
        if not self.api_key:
            logger.warning("Tavily API Key is missing. Web search will be bypassed.")

    async def _search_query_with_retry(self, client: httpx.AsyncClient, query: str, max_retries: int = 3) -> List[Dict[str, Any]]:
        if not self.api_key: return []
        payload = {"api_key": self.api_key, "query": query, "search_depth": "advanced", "max_results": 5, "include_answer": True, "include_raw_content": True}
        delay = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                res = await client.post(self.api_url, json=payload, timeout=10.0)
                if res.status_code == 429:
                    logger.warning(f"Tavily Rate Limit hit (429) for query '{query}'. Retrying in {delay}s...")
                elif res.status_code in {401, 403}:
                    logger.error("Tavily Unauthorized. Check API Key.")
                    return []
                else:
                    res.raise_for_status()
                    return res.json().get("results", [])
            except Exception as e:
                logger.warning(f"Timeout/HTTP error during search (Attempt {attempt}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2.0
        return []

    async def _generate_optimal_queries(self, cert_data: Any) -> List[str]:
        groq_key = os.getenv("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
        if not groq_key:
            terms = [f'"{cert_data.certificate_name}"'] if cert_data.certificate_name.lower() != "n/a" else []
            if cert_data.issuer.lower() != "n/a": terms.append(cert_data.issuer)
            if cert_data.skills: terms.extend(cert_data.skills[:2])
            return [" ".join(terms) + " event details"] if terms else ["certificate verification event details"]
        try:
            from openai import OpenAI
            from app.utils.json_parser import parse_llm_json
            client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            prompt = f'Generate 3 highly optimized web search queries to find the official event page, course description, or registration details for Name: {cert_data.certificate_name}, Issuer: {cert_data.issuer}, Date: {cert_data.date}, Skills: {", ".join(cert_data.skills)}. Output strict JSON array: {{ "queries": ["query 1", "query 2", "query 3"] }}'
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, lambda: client.chat.completions.create(
                model="llama-3.1-8b-instant", messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}, temperature=0.3
            ))
            return parse_llm_json(res.choices[0].message.content).get("queries", [])[:3]
        except Exception as e:
            logger.warning(f"Failed to generate LLM search queries: {e}")
            return [f'"{cert_data.certificate_name}" event details {cert_data.issuer}', f'who conducted "{cert_data.certificate_name}"', f'"{cert_data.certificate_name}" purpose course date']

    async def search_certificate_event(self, cert_data: Any) -> List[Dict[str, Any]]:
        import re
        if not self.api_key: return []
        c_name, c_issuer = (cert_data.certificate_name or "").strip(), (cert_data.issuer or "").strip()
        if not c_name and not c_issuer and not cert_data.skills: return []
        queries = await self._generate_optimal_queries(cert_data)
        logger.info(f"Generated search queries: {queries}")
        async with httpx.AsyncClient() as client:
            tasks = [self._search_query_with_retry(client, q) for q in queries]
            res_list = await asyncio.gather(*tasks, return_exceptions=True)
        aggregated = {}

        for res in res_list:
            if isinstance(res, Exception): continue
            for item in res:
                url = item.get("url")
                if url and url.startswith("http") and url not in aggregated:
                    aggregated[url] = {
                        "title": item.get("title", "No Title"), "snippet": item.get("content", ""),
                        "url": url, "score": item.get("score", 0.0), "raw_content": item.get("raw_content", "")
                    }
        unique = list(aggregated.values())
        
        # Apply Programmatic Domain Boosting & Word Overlap Relevance Scoring
        for item in unique:
            url_lower = item.get("url", "").lower()
            score = item.get("score", 0.0)
            
            # Boost score for verified trusted domains
            trusted_domains = [".edu", ".org", "amazon.com", "coursera.org", "github.com", "udemy.com", "microsoft.com", "google.com"]
            if any(domain in url_lower for domain in trusted_domains):
                score += 0.35
                
            # Boost score based on word overlap with certificate name
            words_cert = set(re.findall(r'\w+', c_name.lower()))
            words_snippet = set(re.findall(r'\w+', item.get("snippet", "").lower()))
            overlap = len(words_cert & words_snippet)
            score += overlap * 0.05
            
            item["score"] = score
            
        unique.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return unique
