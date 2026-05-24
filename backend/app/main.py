import os
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environmental configs
load_dotenv(override=True)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("certificate_intelligence")

# Ensure required directories are created at bootstrap
from app.utils.db_cache import get_cache
from app.utils.file_handler import FileHandler

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for startup and shutdown execution."""
    logger.info("===========================================")
    logger.info("Initializing Certificate Intelligence Backend")
    logger.info("=========================================== ")
    
    # Setup cache database
    get_cache()
    
    # Setup Email intelligence SQLite database
    from app.models.database import init_db
    init_db()
    logger.info("Email intelligence SQL metadata database initialized.")
    
    logger.info(f"DEBUG: Active GROQ_MODEL from environment: {os.getenv('GROQ_MODEL', 'llama-3.1-70b-versatile')}")
    
    # Setup upload handler
    FileHandler()
    
    yield
    
    logger.info("Shutting down Certificate Intelligence Backend...")

# Create FastAPI instance
app = FastAPI(
    title="Agentic Certificate Intelligence Backend",
    description="Asynchronous metadata extraction, Tavily-powered search, and LLM-driven event synthesis",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for direct frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
from app.api.routes import router as api_router
from app.api.email_routes import router as email_router
app.include_router(api_router, tags=["Intelligence Engine"])
app.include_router(email_router, tags=["Email Intelligence Engine"])

@app.get("/")
async def get_root_status():
    """
    Returns the basic health status of the Agentic Certificate Intelligence Backend.
    """
    return {
        "status": "Engine Node Active",
        "service": "Agentic Certificate Intelligence API"
    }
