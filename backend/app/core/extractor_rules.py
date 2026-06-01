import re, difflib
from typing import List, Dict, Any

KNOWN_ISSUERS = ["Coursera", "Udemy", "Stanford University", "Stanford", "MIT", 
                 "Massachusetts Institute of Technology", "Microsoft", "Amazon Web Services", 
                 "AWS", "Google", "Google Cloud", "Apache", "Apache Software Foundation",
                 "Harvard University", "Harvard", "EdX", "Linux Foundation"]

SKILLS_DICTIONARY = {"python", "fastapi", "react", "docker", "kubernetes", "aws", "flink", 
                     "javascript", "golang", "machine learning", "deep learning", "ai", 
                     "datascience", "sql", "postgresql", "sqlite", "html", "css", "nodejs", 
                     "git", "github", "ci/cd", "rest api", "cloud computing", "c++", "java",
                     "devops", "typescript", "terraform", "django", "flask", "apache flink"}

MONTH_MAP = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
             "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
             "january": "01", "february": "02", "march": "03", "april": "04", "june": "06",
             "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12"}

def standardize_date(text: str) -> str:
    if not text: return "N/A"
    iso_match = re.search(r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b', text)
    if iso_match: return f"{iso_match.group(1)}-{int(iso_match.group(2)):02d}-{int(iso_match.group(3)):02d}"
    std_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', text)
    if std_match: return f"{std_match.group(3)}-{int(std_match.group(2)):02d}-{int(std_match.group(1)):02d}"
    text_lower = text.lower()
    for m_name, m_num in MONTH_MAP.items():
        m1 = re.search(rf'\b{m_name}\s+(\d{4})\b', text_lower)
        if m1: return f"{m1.group(1)}-{m_num}-01"
        m2 = re.search(rf'\b(\d{1,2})\s+{m_name}\s+(\d{4})\b', text_lower)
        if m2: return f"{m2.group(2)}-{m_num}-{int(m2.group(1)):02d}"
        m3 = re.search(rf'\b{m_name}\s+(\d{1,2}),?\s+(\d{4})\b', text_lower)
        if m3: return f"{m3.group(2)}-{m_num}-{int(m3.group(1)):02d}"
    return "N/A"

def extract_recipient(text: str) -> str:
    if not text: return "Unknown Recipient"
    anchors = [
        r'(?:presented to|awarded to|certifies that|conferred upon|this confirms that)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:has successfully completed|completed the course)'
    ]
    for pat in anchors:
        m = re.search(pat, text)
        if m and m.group(1).strip().lower() not in {"this", "the", "a", "an", "has", "successfully", "satisfactorily"}:
            return m.group(1).strip()
    for line in text.splitlines():
        line = line.strip()
        if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$', line): return line
    return "Unknown Recipient"

def extract_issuer_spelling(text: str) -> str:
    if not text: return "Unknown Issuer"
    for issuer in KNOWN_ISSUERS:
        if issuer.lower() in text.lower(): return issuer
    for line in text.splitlines():
        words = line.strip().split()
        if len(words) < 5:
            matches = difflib.get_close_matches(line.strip(), KNOWN_ISSUERS, n=1, cutoff=0.75)
            if matches: return matches[0]
    for line in text.splitlines():
        line = line.strip()
        if any(t in line.lower() for t in ["university", "academy", "foundation", "institute", "corporation", "google", "microsoft", "amazon"]):
            if len(line) < 50: return line
    return "Unknown Issuer"

def extract_skills_programmatic(text: str) -> List[str]:
    if not text: return []
    return sorted(list({skill for skill in SKILLS_DICTIONARY if skill in text.lower()}))

def run_deterministic_extraction(text: str) -> Dict[str, Any]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    cert_name = "Unknown Certificate"
    for l in lines[:5]:
        if any(k in l.lower() for k in ["certificate", "certification", "completion", "degree", "diploma", "awarded"]) and len(l) < 60:
            cert_name = l
            break
    if cert_name == "Unknown Certificate" and lines: cert_name = lines[0]
    recipient = extract_recipient(text)
    return {
        "certificate_name": cert_name,
        "recipient": recipient,
        "issuer": extract_issuer_spelling(text),
        "date": standardize_date(text),
        "skills": extract_skills_programmatic(text),
        "confidence_score": 0.85 if recipient != "Unknown Recipient" else 0.5
    }

