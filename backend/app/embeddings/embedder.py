import os
import asyncio
import logging
from typing import List
import httpx
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("certificate_intelligence.embeddings.embedder")

class AsynchronousEmbedder:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        self.provider = "local"
        self.model_name = "BAAI/bge-large-en-v1.5"
        self.dimensions = 1024
        self.local_model = None

        # if self.gemini_key:
        #     self.provider = "gemini"
        #     self.model_name = "models/embedding-001"
        #     self.dimensions = 768
        #     logger.info("Using Gemini Embeddings (768 dimensions).")
        # else:
        
        logger.info("Initializing Local SentenceTransformers model (bge-large-en-v1.5, 1024 dimensions)...")
        try:
           
            # Lazy-load to avoid slow imports at bootstrap
            self.local_model = SentenceTransformer("BAAI/bge-large-en-v1.5")
            logger.info("Local SentenceTransformers loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load sentence-transformers: {e}. Semantic search fallbacks will fail.")

    async def get_embedding(self, text: str) -> List[float]:
        """Convert a single text chunk into a dense vector embedding."""
        res = await self.get_embeddings_batch([text])
        return res[0] if res else []

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate dense vector embeddings in batch for high performance sync operations."""
        if not texts:
            return []

        # 1. Local Fallback
        if self.provider == "local" or self.local_model:
            loop = asyncio.get_running_loop()
            try:
                # Delegate blocking CPU-heavy local inference to thread pool
                embeddings = await loop.run_in_executor(
                    None,
                    lambda: self.local_model.encode(texts, convert_to_numpy=True).tolist()
                )
                return embeddings
            except Exception as e:
                logger.error(f"Local embedding inference failed: {e}")
                return [[0.0] * self.dimensions for _ in texts]

        # 2. Google Gemini Embeddings
        # if self.provider == "gemini":
        #     try:
        #         url = f"https://generativelanguage.googleapis.com/v1beta/{self.model_name}:embedContent?key={self.gemini_key}"
        #         all_embeddings = []
        #         async with httpx.AsyncClient() as client:
        #             for t in texts:
        #                 payload = {
        #                     "model": self.model_name,
        #                     "content": {"parts": [{"text": t}]}
        #                 }
        #                 response = await client.post(url, json=payload, timeout=20.0)
        #                 response.raise_for_status()
        #                 data = response.json()
        #                 all_embeddings.append(data["embedding"]["values"])
        #         return all_embeddings
        #     except Exception as e:
        #         logger.warning(f"Gemini API Embeddings call failed: {e}. Falling back to zero-vectors.")
        #         return [[0.0] * self.dimensions for _ in texts]

        return [[0.0] * self.dimensions for _ in texts]

# Singleton helper
_embedder_instance = None

def get_embedder() -> AsynchronousEmbedder:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = AsynchronousEmbedder()
    return _embedder_instance
