from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://eduzim:eduzim_secret@localhost:5432/reporting_db"
    JWT_SECRET_KEY: str = "dev-jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_ENABLED: bool = False
    SERVICE_NAME: str = "reporting-service"
    APP_NAME: str = "EduZim Reporting Service"
    DEBUG: bool = False

    # Downstream service URLs (for dropout intelligence)
    STUDENT_SERVICE_URL: str = "http://student-service:8000"
    ATTENDANCE_SERVICE_URL: str = "http://attendance-service:8000"
    FEES_SERVICE_URL: str = "http://fees-service:8000"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
