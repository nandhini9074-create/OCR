import time, logging
from pathlib import Path
from typing import Dict, Any, Optional

from app.utils.db_cache import get_cache
from app.core.ocr_engine import get_ocr_engine
from app.core.extractor import CertificateExtractor
from app.core.email_reader import EmailReader
from app.core.email_parser import EmailParser
from app.core.matcher import CertificateEmailMatcher
from app.core.search_engine import TavilySearchEngine
from app.core.event_analyzer import EventAnalyzer
from app.core.pipeline_email import process_email_linkage
from app.schemas.models import CertificateData, EmailIntelligence, EventIntelligence, AnalysisResponse

logger = logging.getLogger("certificate_intelligence.pipeline")

# Used to act as the main controller tying together all individual AI/search modules
class CertificateIntelligencePipeline:
    # Used to initialize all models and APIs once in memory to avoid redundant setups
    def __init__(self):
        self.ocr_engine = get_ocr_engine()
        self.extractor = CertificateExtractor()
        self.email_reader = EmailReader()
        self.email_parser = EmailParser()
        self.matcher = CertificateEmailMatcher()
        self.search_engine = TavilySearchEngine()
        self.event_analyzer = EventAnalyzer()
        self.cache = get_cache()

    # Used as the primary entry point to trigger the full 4-step intelligence pipeline
    async def analyze_certificate(self, file_path: Path, file_hash: str, email: Optional[str] = None) -> AnalysisResponse:
        import shutil, json
        temp_dir = Path("temp_pipeline_dumps")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(exist_ok=True)

        # Used to measure how long the full pipeline takes for UI performance tracking
        start_time = time.time()
        logger.info(f"Pipeline triggered for file: {file_path.name} (Hash: {file_hash}) with email: {email}")
        
        # Used to instantly return results if this exact file was uploaded before (saves API cost)
        cached = self.cache.get_pipeline(file_hash)
        if cached:
            t = time.time() - start_time
            logger.info(f"Duplicate certificate detected! Returning cached response in {t:.2f}s")
            return AnalysisResponse(
                certificate_data=CertificateData(**cached["certificate_data"]), email_intelligence=EmailIntelligence(**cached["email_intelligence"]),
                event_intelligence=EventIntelligence(**cached["event_intelligence"]), confidence_score=cached.get("confidence_score", 0.8),
                cached=True, execution_time_seconds=t, raw_ocr_text=cached.get("raw_ocr_text", ""),
                ocr_method=cached.get("ocr_method", "") or "Pipeline Cache Hit", raw_search_results=cached.get("raw_search_results", [])
            )
            
        # Used to skip running the slow OCR again if we only partially cached the text earlier
        raw_ocr_text = self.cache.get_ocr(file_hash)
        ocr_method = "OCR Cache Hit"
        if not raw_ocr_text:
            # Used to physically read text from the image if it is completely new
            raw_ocr_text, ocr_method = await self.ocr_engine.extract_text(file_path)
            if raw_ocr_text.strip(): self.cache.save_ocr(file_hash, raw_ocr_text)
            
        # Step 1: Used to convert raw image text into structured JSON metadata via LLM
        cert_data = await self.extractor.extract_certificate_data(raw_ocr_text)
        with open(temp_dir / "temp_ocr_extraction.json", "w", encoding="utf-8") as f:
            f.write(cert_data.model_dump_json(indent=4))
        
        search_results = []
        try: 
            # Step 2: Used to fetch internet background context about the certificate/course
            search_results = await self.search_engine.search_certificate_event(cert_data=cert_data)
            with open(temp_dir / "temp_tavily_search.json", "w", encoding="utf-8") as f:
                json.dump(search_results, f, indent=4)
        except Exception as e: logger.error(f"Failed web search: {e}")
        
        # Step 3: Used to dynamically search the user's inbox and AI vector DB to find the exact receipt
        email_intel, email_parsed, conf = await process_email_linkage(
            email=email, file_path_name=file_path.name, raw_ocr_text=raw_ocr_text, cert_data=cert_data,
            search_results=search_results, email_reader=self.email_reader, email_parser=self.email_parser, matcher=self.matcher
        )
        
        with open(temp_dir / "temp_email_abstracted.json", "w", encoding="utf-8") as f:
            dump_data = {
                "raw_email_details": email_intel.model_dump() if email_intel else {},
                "abstracted_details": email_parsed if email_parsed else {}
            }
            json.dump(dump_data, f, indent=4)
        
        # Step 4: Used to merge OCR, Email, and Web data into one final flawless report
        event_intel = await self.event_analyzer.analyze_event(cert_data=cert_data, search_results=search_results, email_data=email_parsed)
        
        execution_time = time.time() - start_time
        # Used to boost the final confidence score if a matching email receipt was found
        agg_conf = round((cert_data.confidence_score + conf) / 2.0, 2) if email_intel.matched_email else cert_data.confidence_score
        
        # Used to bundle all gathered intelligence into the strict output schema
        response = AnalysisResponse(
            certificate_data=cert_data, email_intelligence=email_intel, event_intelligence=event_intel,
            confidence_score=agg_conf, cached=False, execution_time_seconds=round(execution_time, 3),
            raw_ocr_text=raw_ocr_text, ocr_method=ocr_method, raw_search_results=search_results
        )
        
        # Used to memorize this entire result so future uploads of the same file are instant
        self.cache.save_pipeline(file_hash, response.model_dump())
        logger.info(f"Pipeline complete in {execution_time:.3f}s. Confidence Score: {agg_conf}")
        return response

_pipeline_instance = None

# Used to enforce the Singleton pattern so only one pipeline object exists across the entire server
def get_pipeline() -> CertificateIntelligencePipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = CertificateIntelligencePipeline()
    return _pipeline_instance
