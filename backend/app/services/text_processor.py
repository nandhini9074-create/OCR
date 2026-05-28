import re
from typing import List

class EmailTextProcessor:
    def __init__(self, chunk_size: int = 100, chunk_overlap: int = 50):
        self.chunk_size, self.chunk_overlap = chunk_size, chunk_overlap

    def clean_html(self, html: str) -> str:
        if not html: return ""
        text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html)
        text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', text)
        for t, r in [(r'<br\s*/?>', '\n'), ('</p>', '\n\n'), ('</div>', '\n'), ('</li>', '\n'), ('<[^>]+>', '')]:
            text = re.sub(t, r, text)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        for ent, rep in [(r'\r\n', '\n'), (r'\n{3,}', '\n\n'), (r' {2,}', ' ')]:
            text = re.sub(ent, rep, text)
        return text.strip()

    def remove_signature(self, text: str) -> str:
        if not text: return ""
        lines = text.split("\n")
        if len(lines) < 6: return text
        start_idx = int(len(lines) * 0.7)
        markers = [r'^--\s*$', r'^\s*best\s+regards', r'^\s*sincerely', r'^\s*kind\s+regards', r'^\s*thanks\s*,\s*$', r'^\s*regards\s*,\s*$', r'^\s*warm\s+regards', r'^\s*thank\s+you\s*,\s*$', r'^\s*cheers', r'^\s*sent\s+from\s+my']
        for i in range(start_idx, len(lines)):
            if any(re.search(pat, lines[i].lower().strip()) for pat in markers):
                return "\n".join(lines[:i]).strip()
        return text

    def chunk_text(self, text: str) -> List[str]:
        if not text: return []
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) <= self.chunk_size: return [text]
        chunks, start = [], 0
        while start < len(text):
            end = start + self.chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break
            idx = text.rfind(". ", start, end)
            if idx == -1 or idx < start + (self.chunk_size // 2):
                idx = text.rfind(" ", start, end)
            if idx != -1 and idx > start:
                chunks.append(text[start:idx].strip())
                start = idx + 1
            else:
                chunks.append(text[start:end].strip())
                start = end - self.chunk_overlap
        return [c for c in chunks if len(c) > 20]

_processor_instance = None

def get_text_processor() -> EmailTextProcessor:
    global _processor_instance
    if _processor_instance is None: _processor_instance = EmailTextProcessor()
    return _processor_instance
