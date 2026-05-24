import os, asyncio, logging
from typing import Dict, Any, List
from openai import OpenAI
from app.embeddings.embedder import get_embedder
from app.qdrant import get_qdrant_store

logger = logging.getLogger("certificate_intelligence.rag.rag_engine")

class RAGEngine:
    def __init__(self):
        self.embedder, self.qdrant = get_embedder(), get_qdrant_store()
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        if not self.groq_key:
            logger.warning("Groq API Key is missing. RAG summaries will use a fallback text synthesizer.")

    async def execute_rag_query(self, user_id: str, query: str, limit: int = 6) -> Dict[str, Any]:
        logger.info(f"RAG query from user '{user_id}': '{query}'")
        query_vector = await self.embedder.get_embedding(query)
        if not query_vector:
            return {"query": query, "matches": [], "summary": "Error: Failed to generate query embedding vector."}

        hits = await self.qdrant.search_semantic(user_id=user_id, query_vector=query_vector, limit=limit, score_threshold=0.20)
        if not hits:
            logger.info("Qdrant semantic search returned 0 matches.")
            return {"query": query, "matches": [], "summary": "I searched your mailbox thoroughly but could not find any emails relevant to your query. Please make sure your inbox is fully synchronized."}

        context_blocks = [
            f"Source [{idx}]:\n- Email ID: {hit['email_id']}\n- From: {hit['sender']}\n- Subject: {hit['subject']}\n- Date: {hit['timestamp']}\n- Matching Score: {hit['score']:.2f}\n- Excerpt Content: {hit['chunk_text']}\n"
            for idx, hit in enumerate(hits, 1)
        ]
        matches = [{
            "email_id": hit["email_id"], "subject": hit["subject"], "sender": hit["sender"],
            "snippet": hit["chunk_text"], "score": round(hit["score"], 2), "timestamp": hit["timestamp"],
            "thread_id": hit.get("thread_id", "N/A")
        } for hit in hits]

        summary = await self._synthesize_llm_response(query, "\n---\n".join(context_blocks)) if self.groq_key else (
            f"Offline Fallback Answer:\nFound {len(hits)} matching email records. "
            f"The most relevant email was from '{hits[0]['sender']}' with subject '{hits[0]['subject']}'. "
            f"Content snippet: \"{hits[0]['chunk_text'][:200]}...\""
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
                    temperature=0.2, max_tokens=600
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
