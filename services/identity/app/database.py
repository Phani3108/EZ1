from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings

settings = get_settings()

# PH4-1: pool config standardized across services per the audit's Phase 4
# spec. 20 + 40 overflow handles ~60 concurrent in-flight queries per service
# instance; pool_recycle re-establishes connections every hour to dodge
# Postgres tcp_keepalive / NAT timeouts; pre-ping protects against stale
# socket reuse after a Postgres restart.
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
