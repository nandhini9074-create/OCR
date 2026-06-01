import logging
from sqlalchemy import text
from app.models.base import Base, engine

# Load all models for registry
from app.models.user_token import User, OAuthToken
from app.models.email_meta import EmailMetadata, SyncLog
from app.models.cache_models import OCRCache, PipelineCache

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Dynamic schema migration and trigger synchronization for PostgreSQL target
    if engine.url.drivername.startswith("postgresql"):
        try:
            with engine.begin() as conn:
                # 1. Add 'body' column if missing
                conn.execute(text("ALTER TABLE email_metadata ADD COLUMN IF NOT EXISTS body TEXT;"))
                # 2. Add 'search_vector' column if missing
                conn.execute(text("ALTER TABLE email_metadata ADD COLUMN IF NOT EXISTS search_vector tsvector;"))
                # 3. Create GIN index on search_vector if missing
                conn.execute(text("CREATE INDEX IF NOT EXISTS email_search_idx ON email_metadata USING gin(search_vector);"))
                # 4. Create FTS trigger function to auto-parse search vector from subject & body
                conn.execute(text("""
                    CREATE OR REPLACE FUNCTION email_search_trigger() RETURNS trigger AS $$
                    begin
                      new.search_vector :=
                         setweight(to_tsvector('english', coalesce(new.subject,'')), 'A') ||
                         setweight(to_tsvector('english', coalesce(new.body,'')), 'B');
                      return new;
                    end
                    $$ LANGUAGE plpgsql;
                """))
                # 5. Create the trigger
                conn.execute(text("""
                    DROP TRIGGER IF EXISTS tsvectorupdate ON email_metadata;
                    CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE ON email_metadata
                    FOR EACH ROW EXECUTE PROCEDURE email_search_trigger();
                """))
                # 6. Backfill existing records with null search_vector
                conn.execute(text("""
                    UPDATE email_metadata 
                    SET search_vector = 
                        setweight(to_tsvector('english', coalesce(subject,'')), 'A') ||
                        setweight(to_tsvector('english', coalesce(body,'')), 'B')
                    WHERE search_vector IS NULL;
                """))
        except Exception as e:
            logging.getLogger("certificate_intelligence.database").warning(f"PostgreSQL FTS migration bypassed: {e}")
