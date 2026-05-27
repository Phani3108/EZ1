from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://eduzim:eduzim_secret@localhost:5432/fees_db"
    # JWT — REQUIRED via env (no in-code default; BUG-003)
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_ENABLED: bool = False
    SERVICE_NAME: str = "fees-service"
    APP_NAME: str = "EduZim Fees Service"
    DEBUG: bool = False

    # Paynow Zimbabwe
    PAYNOW_INTEGRATION_ID: str = ""
    PAYNOW_INTEGRATION_KEY: str = ""
    PAYNOW_RESULT_URL: str = "https://api.eduzim.co.zw/api/v1/fees/payments/webhook/paynow"
    PAYNOW_RETURN_URL: str = "https://admin.eduzim.co.zw/fees/payment-complete"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
