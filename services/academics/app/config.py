"""academics service config (PH2-5 shell).

JWT_SECRET_KEY is required from env (BUG-003). Service URL settings exist so
the future intra-process authz module can fall back to HTTP calls during the
transitional PH2-6→9 work.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://eduzim:eduzim_secret@localhost:5432/academics_db"
    # PH2-11 — academics now serves /api/v1/reports/* by opening a SECOND
    # connection pool against the reporting projection DB (writes still
    # happen inside the reporting-service consumer process). Defaults to a
    # local sqlite file for unit tests; prod compose overrides with the real
    # postgres URL.
    REPORTING_DATABASE_URL: str = "sqlite:///./test_reporting_ro.db"
    # JWT — REQUIRED via env (no in-code default; BUG-003)
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_ENABLED: bool = False
    SERVICE_NAME: str = "academics"
    APP_NAME: str = "EduZim Academics Service"
    DEBUG: bool = False

    # Internal service token — REQUIRED via env (no in-code default; BUG-004)
    INTERNAL_SERVICE_TOKEN: str

    # PH2-12: the PH2-6→9 burn-in URLs (SCHOOL/STUDENT/ATTENDANCE/
    # ASSESSMENT_SERVICE_URL) have been removed — the corresponding
    # services are deleted and there's no in-process call site that
    # falls back to HTTP anymore.
    IDENTITY_SERVICE_URL: str = "http://identity:8000"
    # PH2-11 — dropout intelligence still calls finance for invoice data
    # (fees stayed a separate service per ADR 006). The other two HTTP hops
    # the old reporting-service made (students, attendance) are gone:
    # academics owns those tables in-process now.
    FINANCE_SERVICE_URL: str = "http://finance:8000"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
