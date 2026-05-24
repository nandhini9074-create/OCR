import re, os
from typing import List, Any, Optional

KEYWORDS = ["certificate", "completion", "workshop", "internship", "hackathon", "training", "course", "webinar", "credential", "publication", "published", "award", "recognition", "participation", "event", "achievement", "bootcamp", "program", "scholar"]

def build_dynamic_keywords(cert: Optional[Any] = None, fname: Optional[str] = None) -> List[str]:
    kws = list(KEYWORDS)
    if cert:
        for attr, skip in [("certificate_name", "certificate"), ("issuer", "corporation company limited incorporated")]:
            val = getattr(cert, attr, "")
            if val and val.strip().lower() not in {"n/a", "unknown", "extraction failed"}:
                kws.extend([re.sub(r'\W+', '', w).lower() for w in val.split() if len(w) > 3 and w not in skip.split()])
                kws.append(val.lower())
        for skill in getattr(cert, "skills", []):
            if skill and skill.strip():
                kws.extend([re.sub(r'\W+', '', w).lower() for w in skill.split() if len(w) > 3])
                kws.append(skill.lower())
    if fname:
        base = os.path.splitext(fname)[0]
        kws.extend([re.sub(r'\W+', '', w).lower() for w in re.split(r'[_\-\s]', base) if len(w) > 3 and w not in {"certificate", "receipt", "invoice", "upload", "scan", "copy", "n/a"}])
        kws.append(base.lower())
    return list({k.strip().lower() for k in kws if k and len(k.strip()) > 2 and k.strip().lower() not in {"n/a", "unknown", "extraction failed", "nan"}})
