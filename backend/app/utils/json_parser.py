import re
import json
import logging
from typing import Dict, Any

logger = logging.getLogger("certificate_intelligence.json_parser")

def clean_json_string(text: str) -> str:
    """Strip markdown code block wrappers (e.g. ```json ... ```) to extract a clean JSON string."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text

def parse_llm_json(raw_response: str) -> Dict[str, Any]:
    """Defensively parse JSON from LLM response, with fallback handling."""
    cleaned_text = clean_json_string(raw_response)
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding error: {e}. Raw response: {raw_response}")
        try:
            start_idx = cleaned_text.find("{")
            end_idx = cleaned_text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                json_str = cleaned_text[start_idx:end_idx + 1]
                return json.loads(json_str)
        except Exception as inner_e:
            logger.error(f"Fallback JSON parsing failed: {inner_e}")
        raise ValueError("Could not parse valid JSON from LLM response.")
