import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.schemas.models import CertificateData
from app.qdrant import get_qdrant_store
from app.embeddings.embedder import get_embedder

logger = logging.getLogger("certificate_intelligence.pipeline_qdrant")

async def search_qdrant_emails(cert: CertificateData, email: Optional[str]) -> List[Dict[str, Any]]:
    try:
        qp = []
        if cert.certificate_name and cert.certificate_name.lower() != "n/a": qp.append(f"Certificate: {cert.certificate_name}")
        if cert.issuer and cert.issuer.lower() != "n/a": qp.append(f"issued by {cert.issuer}")
        if cert.recipient and cert.recipient.lower() != "n/a": qp.append(f"to {cert.recipient}")
        if cert.skills: qp.append(f"for skills in {', '.join(cert.skills)}")
        if cert.date and cert.date.lower() != "n/a": qp.append(f"on {cert.date}")
        q_text = " ".join(qp) if qp else "congratulations certificate registration completion"
        logger.info(f"Generating query embedding for search: '{q_text}'")
        q_vector = await get_embedder().get_embedding(q_text)
        hits = await get_qdrant_store().search_semantic(user_id=email or "alex@example.com", query_vector=q_vector, limit=5, score_threshold=0.3)
        return [{
            "id": h["email_id"], "subject": h["subject"], "sender": h["sender"],
            "date": h.get("timestamp").isoformat() if isinstance(h.get("timestamp"), datetime) else (h.get("timestamp") or "N/A"),
            "body": h["chunk_text"], "attachments": [], "has_matching_attachment": False, "from_qdrant": True
        } for h in hits]
    except Exception as qe:
        logger.warning(f"Qdrant email lookup bypassed or failed: {qe}"); return []
