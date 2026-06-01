import time, logging
from pathlib import Path
from typing import Optional
from app.utils.db_cache import get_cache
from app.core.ocr_engine import get_ocr_engine
from app.core.extractor import CertificateExtractor
from app.core.email_parser import EmailParser
from app.core.matcher import CertificateEmailMatcher
from app.core.search_engine import TavilySearchEngine
from app.core.event_analyzer import EventAnalyzer
from app.core.pipeline_email import process_email_linkage
from app.core.pipeline_logging import write_benchmark_row
from app.schemas.models import CertificateData, EmailIntelligence, EventIntelligence, AnalysisResponse

logger = logging.getLogger("certificate_intelligence.pipeline")

class CertificateIntelligencePipeline:
    def __init__(self):
        self.ocr_engine, self.extractor, self.email_parser = get_ocr_engine(), CertificateExtractor(), EmailParser()
        self.matcher, self.search_engine, self.event_analyzer, self.cache = CertificateEmailMatcher(), TavilySearchEngine(), EventAnalyzer(), get_cache()

    async def _handle_cache(self, file_hash: str, display_name: str, start_time: float) -> Optional[AnalysisResponse]:
        cached = self.cache.get_pipeline(file_hash)
        if not cached: return None
        t = time.time() - start_time
        logger.info(f"Duplicate certificate detected! Returning cached response in {t:.2f}s")
        res = AnalysisResponse(
            certificate_data=CertificateData(**cached["certificate_data"]),
            email_intelligence=EmailIntelligence(**cached["email_intelligence"]),
            event_intelligence=EventIntelligence(**cached["event_intelligence"]),
            confidence_score=cached.get("confidence_score", 0.8),
            cached=True, execution_time_seconds=t, raw_ocr_text=cached.get("raw_ocr_text", ""),
            ocr_method=cached.get("ocr_method", "") or "Pipeline Cache Hit",
            raw_search_results=cached.get("raw_search_results", [])
        )
        write_benchmark_row(display_name, file_hash, "Full Pipeline Cache Hit", res.ocr_method, 0.0, 0.0, 0.0, 0.0, 0.0, t, res.confidence_score)
        return res

    async def analyze_certificate(self, file_path: Path, file_hash: str, email: Optional[str] = None, original_filename: Optional[str] = None) -> AnalysisResponse:
        start, display_name = time.time(), original_filename or file_path.name
        cached_res = await self._handle_cache(file_hash, display_name, start)
        if cached_res: return cached_res

        # 1. OCR Stage
        ocr_start, raw_ocr_text, ocr_method = time.time(), self.cache.get_ocr(file_hash), "OCR Cache Hit"
        if not raw_ocr_text:
            raw_ocr_text, ocr_method = await self.ocr_engine.extract_text(file_path)
            if raw_ocr_text.strip(): self.cache.save_ocr(file_hash, raw_ocr_text)
        t_ocr = time.time() - ocr_start

        # 2. Extractor Stage
        t_start = time.time()
        cert_data = await self.extractor.extract_certificate_data(raw_ocr_text)
        t_extract = time.time() - t_start

        # 3. Web Search Stage
        t_start, search_results = time.time(), []
        try:
            search_results = await self.search_engine.search_certificate_event(cert_data=cert_data)
        except Exception as e:
            logger.error(f"Failed web search: {e}")
        t_search = time.time() - t_start

        # 4. Email Linkage Stage
        t_start = time.time()
        email_intel, email_parsed, conf = await process_email_linkage(
            email=email, file_path_name=display_name, raw_ocr_text=raw_ocr_text, cert_data=cert_data,
            search_results=search_results, email_parser=self.email_parser, matcher=self.matcher
        )
        t_email = time.time() - t_start

        # 5. Cognitive Merge Stage
        t_start = time.time()
        event_intel = await self.event_analyzer.analyze_event(cert_data=cert_data, search_results=search_results, email_data=email_parsed)
        t_merge = time.time() - t_start

        execution_time = time.time() - start
        agg_conf = round((cert_data.confidence_score + conf) / 2.0, 2) if email_intel.matched_email else cert_data.confidence_score
        
        response = AnalysisResponse(
            certificate_data=cert_data, email_intelligence=email_intel, event_intelligence=event_intel,
            confidence_score=agg_conf, cached=False, execution_time_seconds=round(execution_time, 3),
            raw_ocr_text=raw_ocr_text, ocr_method=ocr_method, raw_search_results=search_results
        )
        self.cache.save_pipeline(file_hash, response.model_dump())
        write_benchmark_row(display_name, file_hash, "Fresh Run", ocr_method, t_ocr, t_extract, t_search, t_email, t_merge, execution_time, agg_conf)
        return response

_pipeline_instance = None

def get_pipeline() -> CertificateIntelligencePipeline:
    global _pipeline_instance
    if _pipeline_instance is None: _pipeline_instance = CertificateIntelligencePipeline()
    return _pipeline_instance

