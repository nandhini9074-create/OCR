from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class CertificateData(BaseModel):
    certificate_name: str = Field(..., description="Name of the certificate, course, or certification")
    recipient: str = Field(..., description="Name of the recipient")
    issuer: str = Field(..., description="Organization or institution that issued the certificate")
    date: str = Field(..., description="Date the certificate was issued (YYYY-MM-DD or N/A)")
    skills: List[str] = Field(default_factory=list, description="Skills, tools, or technologies associated")
    confidence_score: float = Field(default=0.8, description="Confidence score for the extraction accuracy (0.0 to 1.0)")

class EmailIntelligence(BaseModel):
    matched_email: bool = Field(default=False, description="True if relevant email was matched to this certificate")
    email_subject: str = Field(default="N/A", description="Subject line of the matched email")
    email_sender: str = Field(default="N/A", description="Sender address of the matched email")
    email_date: str = Field(default="N/A", description="Date the matched email was sent/received")
    extracted_event_details: str = Field(default="N/A", description="Enriched details extracted from the matched email")
    email_body: str = Field(default="N/A", description="Full content of the matched email")
    warning_message: Optional[str] = Field(default=None, description="Warning/error message explaining linkage bypass/failure")

class EventIntelligence(BaseModel):
    purpose: str = Field(..., description="Primary objective or goal of the certificate event")
    conducted_by: str = Field(..., description="Organization/platform/speaker who conducted the event")
    date: str = Field(..., description="Exact date or duration of the event")
    time: str = Field(..., description="Time of the event or hours required")
    location: str = Field(..., description="Where the event was held")
    description: str = Field(..., description="Concise, comprehensive description of the event")

class AnalysisResponse(BaseModel):
    certificate_data: CertificateData
    email_intelligence: EmailIntelligence
    event_intelligence: EventIntelligence
    confidence_score: float = Field(default=0.8, description="Aggregated pipeline confidence score (0.0 to 1.0)")
    cached: bool = Field(default=False, description="Indicates if result was retrieved from cache")
    execution_time_seconds: float = Field(..., description="Total duration in seconds to perform the analysis")
    raw_ocr_text: str = Field(default="", description="Raw text extracted from certificate")
    ocr_method: str = Field(default="", description="OCR method: 'Digital PDF Text', 'EasyOCR', 'Groq Vision', 'Cache'")
    raw_search_results: List[Dict[str, Any]] = Field(default_factory=list, description="Raw Tavily web search results")
