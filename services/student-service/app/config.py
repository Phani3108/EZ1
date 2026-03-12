from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://eduzim:eduzim_secret@localhost:5432/student_db"
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_ENABLED: bool = False
    SCHOOL_SERVICE_URL: str = "http://school-service:8000"
    SERVICE_NAME: str = "student-service"
    APP_NAME: str = "EduZim Student Service"
    DEBUG: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
