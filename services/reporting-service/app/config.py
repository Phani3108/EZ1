from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://eduzim:eduzim_secret@localhost:5432/reporting_db"
    # JWT — REQUIRED via env (no in-code default; BUG-003)
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_ENABLED: bool = False
    SERVICE_NAME: str = "reporting-service"
    APP_NAME: str = "EduZim Reporting Service"
    DEBUG: bool = False

    # PH2-11/PH2-12: dropout intelligence moved to academics. This
    # consumer doesn't need any downstream service URLs — it only reads
    # Kafka and writes the projection DB.

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
