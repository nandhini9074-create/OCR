# Database access facade for 100% backward compatibility
from app.models.base import Base, engine, SessionLocal, get_db
from app.models.init import init_db
from app.models.user_token import User, OAuthToken
from app.models.email_meta import EmailMetadata, SyncLog
from app.models.cache_models import OCRCache, PipelineCache
