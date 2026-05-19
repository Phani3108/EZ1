from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://eduzim:eduzim_secret@localhost:5432/school_db"
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_ENABLED: bool = False
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    STUDENT_SERVICE_URL: str = "http://student-service:8000"
    INTERNAL_SERVICE_TOKEN: str = "change-me-in-production"
    SERVICE_NAME: str = "school-service"
    APP_NAME: str = "EduZim School Service"
    DEBUG: bool = False

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
