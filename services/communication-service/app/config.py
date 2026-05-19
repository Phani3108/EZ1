from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://eduzim:eduzim_secret@localhost:5432/comm_db"
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_ENABLED: bool = False
    SERVICE_NAME: str = "communication-service"
    APP_NAME: str = "EduZim Communication Service"
    DEBUG: bool = False
    MAX_RETRY_COUNT: int = 3

    # ─── Provider credentials (delivery channels) ───
    # Africa's Talking — SMS
    AFRICASTALKING_API_KEY: str = ""
    AFRICASTALKING_USERNAME: str = "sandbox"
    AFRICASTALKING_SENDER: str = "EduZim"

    # SMTP — Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@eduzim.co.zw"

    # Firebase Cloud Messaging — Push
    FCM_SERVER_KEY: str = ""

    # Meta WhatsApp Business Cloud API
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""

    # Outbox lag thresholds (used by diagnostics deep-probe)
    OUTBOX_LAG_DEGRADED_MINUTES: int = 5
    OUTBOX_LAG_DOWN_MINUTES: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
