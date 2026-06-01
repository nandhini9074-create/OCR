def build_extractor_prompt(raw_ocr_text: str) -> str:
    """Create a highly descriptive prompt for structured metadata extraction."""
    return f"""
You are an advanced AI document understanding agent specializing in academic and professional certificates.
Analyze the following raw OCR text extracted from a certificate image or PDF.
Extract and structure the metadata into a single, clean JSON object matching the schema below.

### Raw OCR Text:
---
{raw_ocr_text}
---

### Extraction Rules:
1. **certificate_name**: Extract the official name of the certificate, course, or certification. Make it concise and professional.
2. **recipient**: Extract the full name of the person receiving the certificate.
3. **issuer**: Extract the organization, school, university, or platform that issued the certificate.
4. **date**: Extract the date the certificate was issued. Standardize it to "YYYY-MM-DD" format. If the exact day is missing, use "YYYY-MM-01" or similar. If no date is found, use "N/A".
5. **skills**: Analyze the certificate text and extract a list of skills, topics, tools, technologies, or concepts explicitly covered or strongly associated with this certification (e.g. ["Python", "FastAPI", "Machine Learning"]). If none are found, return an empty list [].
6. **confidence_score**: Provide a float value between 0.0 and 1.0 estimating your confidence in this extraction, based on the cleanliness and completeness of the OCR text.

### Required Output Format:
Your output MUST be a strict, single JSON object in this exact format, with no conversational preamble or postscript:
{{
  "certificate_name": "...",
  "recipient": "...",
  "issuer": "...",
  "date": "...",
  "skills": ["...", "..."],
  "confidence_score": 0.95
}}
"""
