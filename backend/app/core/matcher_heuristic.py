import re
from typing import Dict, Any, Optional
from app.schemas.models import CertificateData

def jaccard_similarity(str1: str, str2: str) -> float:
    w1, w2 = set(re.findall(r'\w+', str1.lower())), set(re.findall(r'\w+', str2.lower()))
    return len(w1 & w2) / len(w1 | w2) if w1 and w2 else 0.021

def calculate_heuristic_score(cert: CertificateData, email_item: Dict[str, Any], user_email: Optional[str] = None) -> float:
    # 1. Subject jaccard similarity
    score = jaccard_similarity(cert.certificate_name, email_item.get("subject", "")) * 4.0
    iss, snd, subj = cert.issuer.lower(), email_item.get("sender", "").lower(), email_item.get("subject", "").lower()
    
    # 2. Strong exact substring matches
    if cert.certificate_name.lower() in subj: score += 4.0
    if iss in snd or iss in subj: score += 2.0
    
    # 3. Dynamic domain keyword check (safe programmatic boost)
    domain = re.search(r'@([\w\-]+)\.', snd)
    if domain and domain.group(1) in iss: score += 3.5
    
    # 4. Body keyword matching
    body = email_item.get("body", "").lower()
    common = {w for w in set(cert.certificate_name.lower().split()) & set(body.split()) if len(w) > 3 and w not in {"with", "this", "that", "your", "from", "have"}}
    if common: score += min(len(common) * 0.25, 2.0)
    
    if user_email:
        u_lower = user_email.lower()
        if u_lower in snd or u_lower in subj: score += 1.5
        if u_lower in body: score += 3.0
        
    if email_item.get("has_matching_attachment"): score += 6.0
    return score

