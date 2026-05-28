import os, uuid, logging
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, Filter, FieldCondition, MatchValue
from app.embeddings.embedder import get_embedder

logger = logging.getLogger("certificate_intelligence.qdrant.qdrant_client")

class QdrantVectorStore:
    def __init__(self):
        self.collection_name, self.embedder = "emails_semantic_collection", get_embedder()
        url, host, port, key = os.getenv("QDRANT_URL"), os.getenv("QDRANT_HOST"), os.getenv("QDRANT_PORT"), os.getenv("QDRANT_API_KEY")
        if url:
            logger.info(f"Connecting to Qdrant Cloud at: {url}")
            self.client = QdrantClient(url=url, api_key=key)
        elif host and port:
            logger.info(f"Connecting to Qdrant Server at: {host}:{port}")
            self.client = QdrantClient(host=host, port=int(port), api_key=key)
        else:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache", "qdrant")
            os.makedirs(cache_dir, exist_ok=True)
            logger.info(f"Using Embedded Qdrant local storage at: {cache_dir}")
            self.client = QdrantClient(path=cache_dir)
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            if self.collection_name not in [col.name for col in self.client.get_collections().collections]:
                logger.info(f"Creating collection '{self.collection_name}' ({self.embedder.dimensions} dims)...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.embedder.dimensions, distance=Distance.COSINE)
                )
                for f in ["user_id", "email_id"]:
                    self.client.create_payload_index(collection_name=self.collection_name, field_name=f, field_schema=models.PayloadSchemaType.KEYWORD)
                logger.info("Qdrant collection initialized with payload indexes.")
            else:
                logger.info(f"Confirmed collection '{self.collection_name}' exists.")
        except Exception as e:
            logger.critical(f"Failed to bootstrap collection: {e}")

    async def upsert_email_chunks(self, chunks: List[Dict[str, Any]]) -> bool:
        if not chunks: return True
        try:
            p_keys = ["user_id", "email_id", "subject", "sender", "recipients", "timestamp", "thread_id", "chunk_text", "importance_score"]
            points = [
                models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{ch['email_id']}_{ch['chunk_text'][:50]}")),
                    vector=ch["vector"],
                    payload={k: ch.get(k, [] if k == "recipients" else (0.0 if k == "importance_score" else "")) for k in p_keys}
                ) for ch in chunks
            ]
            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info(f"Upserted {len(points)} vector chunks into Qdrant.")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert to Qdrant: {e}")
            return False

    async def search_semantic(
        self, user_id: str, query_vector: List[float], limit: int = 6, score_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        try:
            tenant_filter = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
            results = self.client.query_points(
                collection_name=self.collection_name, query=query_vector,
                query_filter=tenant_filter, limit=limit, score_threshold=score_threshold
            ).points
            p_keys = ["user_id", "email_id", "subject", "sender", "recipients", "timestamp", "thread_id", "chunk_text", "importance_score"]
            return [{"id": h.id, "score": h.score, **{k: h.payload.get(k) for k in p_keys}} for h in results]
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def delete_user_vectors(self, user_id: str) -> bool:
        try:
            f = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
            self.client.delete(collection_name=self.collection_name, points_selector=models.FilterSelector(filter=f))
            logger.info(f"Deleted vectors in Qdrant for: '{user_id}'")
            return True
        except Exception as e:
            logger.error(f"Failed to wipe user vectors: {e}")
            return False

_qdrant_instance = None

def get_qdrant_store() -> QdrantVectorStore:
    global _qdrant_instance
    if _qdrant_instance is None:
        _qdrant_instance = QdrantVectorStore()
    return _qdrant_instance

# Trigger reload
