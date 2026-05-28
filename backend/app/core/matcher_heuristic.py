import re
from typing import Dict, Any, Optional
from app.schemas.models import CertificateData

# Used to calculate mathematically how similar two strings are (e.g. matching filenames)
def jaccard_similarity(str1: str, str2: str) -> float:
    # Convert strings into sets of words to easily find intersections
    w1, w2 = set(re.findall(r'\w+', str1.lower())), set(re.findall(r'\w+', str2.lower()))
    return len(w1 & w2) / len(w1 | w2) if w1 and w2 else 0.021

# Used to quickly score and rank emails before sending them to the slower LLM
def calculate_heuristic_score(cert: CertificateData, email_item: Dict[str, Any], user_email: Optional[str] = None) -> float:
    subj = email_item.get("subject", "").lower()
    
    # CRITICAL: Instantly reject Calendar Invites or Briefing Sessions
    if "invitation" in subj or "briefing" in subj or "calendar" in subj or "upcoming session" in subj:
        return -10.0

    # Heavily weight emails where the subject closely matches the certificate name
    score = jaccard_similarity(cert.certificate_name, subj) * 4.0
    # Check if the issuer's name directly appears in the sender name or subject
    iss, snd, subj = cert.issuer.lower(), email_item.get("sender", "").lower(), email_item.get("subject", "").lower()
    if iss in snd or iss in subj: score += 2.0
    # Extract the domain from the sender's email (e.g. 'udemy' from no-reply@udemy.com)
    domain = re.search(r'@([\w\-]+)\.', snd)
    # Give points if the sender's domain matches the issuer's name
    if domain and domain.group(1) in iss: score += 1.5
    # Find meaningful words that appear in both the certificate name and the email body
    body = email_item.get("body", "").lower()
    common = {w for w in set(cert.certificate_name.lower().split()) & set(body.split()) if len(w) > 3 and w not in {"with", "this", "that", "your", "from", "have"}}
    # Award partial points for every matching word found in the body
    if common: score += min(len(common) * 0.25, 2.0)
    # Check if the user's email address is explicitly mentioned in the email
    if user_email:
        u_lower = user_email.lower()
        if u_lower in snd or u_lower in subj: score += 1.5
        if u_lower in body: score += 3.0
    # Massive point boost if the email actually contains an attachment with a similar filename
    if email_item.get("has_matching_attachment"): score += 6.0
    return score
