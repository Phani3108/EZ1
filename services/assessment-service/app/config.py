from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./assessment_test.db"
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    SERVICE_NAME: str = "assessment-service"
    APP_NAME: str = "EduZim Assessment Service"
    DEBUG: bool = False

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:29092"
    KAFKA_TOPIC_PREFIX: str = "eduzim"

    # Internal service communication
    SCHOOL_SERVICE_URL: str = "http://localhost:8002"
    STUDENT_SERVICE_URL: str = "http://localhost:8003"
    INTERNAL_SERVICE_TOKEN: str = "eduzim-internal-secret-change-in-production"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
