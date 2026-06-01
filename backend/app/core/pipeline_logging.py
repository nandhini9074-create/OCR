import os
import datetime
import logging
from pathlib import Path
from app.embeddings.embedder import get_embedder

logger = logging.getLogger("certificate_intelligence.pipeline_logging")

def write_benchmark_row(
    filename: str, file_hash: str, cache_status: str, ocr_method: str,
    t_ocr: float, t_extract: float, t_search: float, t_email: float, t_merge: float,
    total_time: float, conf_score: float
):
    try:
        log_file = Path(__file__).resolve().parents[3] / "pipeline_benchmarks.md"
        headers_exist = log_file.exists()
        
        llm_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        embed_model = get_embedder().model_name
        search_tool = "Tavily Search" if os.getenv("TAVILY_API_KEY") else "Disabled"
        
        row = (
            f"| {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
            f"| `{filename}` "
            f"| {cache_status} "
            f"| {ocr_method} "
            f"| {t_ocr:.3f}s "
            f"| {t_extract:.3f}s "
            f"| {t_search:.3f}s "
            f"| {t_email:.3f}s "
            f"| {t_merge:.3f}s "
            f"| **{total_time:.3f}s** "
            f"| {int(conf_score * 100)}% "
            f"| `{llm_model}` "
            f"| `{embed_model}` "
            f"| {search_tool} |\n"
        )
        
        with open(log_file, "a", encoding="utf-8") as f:
            if not headers_exist:
                f.write("# 📈 Autonomous Pipeline Benchmark & Execution Logs\n\n")
                f.write("This file is automatically updated by the backend core after each analysis run. Use it to track pipeline speeds, execution timings, accuracy, and caching behaviors.\n\n")
                f.write("| Timestamp | Filename | Cache Status | OCR Method | OCR Time | Extractor Time | Web Search Time | Email Linkage Time | Cognitive Merge Time | Total Time | Conf Score | LLM Model | Embedding Model | Search Tool |\n")
                f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
            f.write(row)
        logger.info(f"Performance metrics successfully recorded to: {log_file}")
    except Exception as e:
        logger.error(f"Failed to write performance log: {e}")
