import os, asyncio, logging
from typing import Dict, Any, List
from openai import OpenAI

logger = logging.getLogger("certificate_intelligence.rag.rag_engine")

class RAGEngine:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        if not self.groq_key:
            logger.warning("Groq API Key is missing. RAG summaries will use a fallback text synthesizer.")

    async def execute_rag_query(self, user_id: str, query: str, limit: int = 6) -> Dict[str, Any]:
        logger.info(f"RAG query from user '{user_id}': '{query}'")
        
        from app.models.database import SessionLocal, EmailMetadata
        from sqlalchemy import text
        import re
        
        db = SessionLocal()
        try:
            # 1. Clean and format tsquery terms
            words = re.sub(r'[^\w\s]', '', query).split()
            query_str = " & ".join(w for w in words if w) if words else "certificate"
            logger.info(f"RAG FTS database query: '{query_str}'")
            
            # 2. Query Postgres FTS
            results = db.query(EmailMetadata)\
                .filter(EmailMetadata.user_id == user_id)\
                .filter(text("search_vector @@ to_tsquery('english', :query)"))\
                .params(query=query_str)\
                .order_by(text("ts_rank(search_vector, to_tsquery('english', :query)) DESC"))\
                .params(query=query_str)\
                .limit(limit)\
                .all()
        except Exception as e:
            logger.error(f"FTS lookup failed during RAG query: {e}")
            results = []
        finally:
            db.close()
            
        if not results:
            logger.info("PostgreSQL FTS returned 0 matches for RAG.")
            return {"query": query, "matches": [], "summary": "I searched your mailbox thoroughly but could not find any emails relevant to your query. Please make sure your inbox is fully synchronized."}

        context_blocks = [
            f"Source [{idx}]:\n- Email ID: {r.email_id}\n- From: {r.sender}\n- Subject: {r.subject}\n- Date: {r.timestamp}\n- Excerpt Content: {r.body}\n"
            for idx, r in enumerate(results, 1)
        ]
        matches = [{
            "email_id": r.email_id, "subject": r.subject or "No Subject", "sender": r.sender or "Unknown",
            "snippet": r.body[:250] + "..." if r.body and len(r.body) > 250 else (r.body or ""), "score": 1.0, "timestamp": str(r.timestamp),
            "thread_id": r.thread_id or "N/A"
        } for r in results]

        summary = await self._synthesize_llm_response(query, "\n---\n".join(context_blocks)) if self.groq_key else (
            f"Offline Fallback Answer:\nFound {len(results)} matching email records. "
            f"The most relevant email was from '{results[0].sender}' with subject '{results[0].subject}'. "
            f"Content snippet: \"{results[0].body[:200]}...\""
        )
        return {"query": query, "matches": matches, "summary": summary}

    async def _synthesize_llm_response(self, query: str, context: str) -> str:
        prompt = f"You are an advanced Enterprise Email Intelligence AI Agent.\nYour task is to answer the user's natural language query using ONLY the verified email context chunks provided below.\n\nSystem Rules:\n1. Ground your answers strictly in the provided sources.\n2. If the context does not contain the answer, say \"Based on your synchronized inbox, I couldn't find details to answer that query.\" Do not fabricate information.\n3. Be professional, direct, and summarize complex threads or email topics clearly.\n4. Attribute facts using clear citation numbers matching the Source index (e.g. \"[1]\", \"[2]\") when referencing specific emails.\n\n### Synchronized Email Context:\n---\n{context}\n---\n\n### User Query:\n\"{query}\"\n\nPlease output a beautifully written, cohesive, and concise markdown-formatted response:"
        try:
            client = OpenAI(api_key=self.groq_key, base_url="https://api.groq.com/openai/v1")
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(
                None, lambda: client.chat.completions.create(
                    model=self.groq_model,
                    messages=[
                        {"role": "system", "content": "You are a professional mailbox summarization and retrieval expert."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2, max_tokens=1000
                )
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq RAG response synthesis failed: {e}")
            return f"Failed to synthesize AI summary: {str(e)}"

_rag_instance = None

def get_rag_engine() -> RAGEngine:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGEngine()
    return _rag_instance
