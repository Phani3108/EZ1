from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://eduzim:eduzim_secret@localhost:5432/attendance_db"
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_ENABLED: bool = False
    REDIS_URL: str = "redis://localhost:6379/2"
    REDIS_ENABLED: bool = False
    STUDENT_SERVICE_URL: str = "http://student-service:8000"
    SCHOOL_SERVICE_URL: str = "http://school-service:8000"
    INTERNAL_SERVICE_TOKEN: str = "change-me-in-production"
    SERVICE_NAME: str = "attendance-service"
    APP_NAME: str = "EduZim Attendance Service"
    DEBUG: bool = False

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
