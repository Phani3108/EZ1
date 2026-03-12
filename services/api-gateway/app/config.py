from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    JWT_SECRET_KEY: str = "dev-jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    SERVICE_NAME: str = "api-gateway"
    APP_NAME: str = "EduZim API Gateway"
    DEBUG: bool = False

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002"

    # Redis for rate limiting
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = False

    # Downstream service URLs
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    SCHOOL_SERVICE_URL: str = "http://localhost:8002"
    STUDENT_SERVICE_URL: str = "http://localhost:8003"
    ATTENDANCE_SERVICE_URL: str = "http://localhost:8004"
    FEES_SERVICE_URL: str = "http://localhost:8005"
    COMMUNICATION_SERVICE_URL: str = "http://localhost:8006"
    REPORTING_SERVICE_URL: str = "http://localhost:8007"
    ASSESSMENT_SERVICE_URL: str = "http://localhost:8008"

    # Rate limiting
    DEFAULT_RATE_LIMIT: int = 60       # req/min/user
    SYNC_RATE_LIMIT: int = 30          # req/min/device for attendance sync
    RATE_LIMIT_WINDOW: int = 60        # seconds

    # Downstream timeouts
    DOWNSTREAM_TIMEOUT: float = 10.0   # seconds
    DOWNSTREAM_CONNECT_TIMEOUT: float = 3.0

    # Retry (GET only by default)
    RETRY_MAX_ATTEMPTS: int = 2        # total attempts for GET retries
    RETRY_BACKOFF: float = 0.3         # seconds between retries

    # Circuit breaker
    CB_FAILURE_THRESHOLD: int = 5      # failures to open circuit
    CB_RECOVERY_TIMEOUT: float = 30.0  # seconds before half-open
    CB_SUCCESS_THRESHOLD: int = 2      # successes to close from half-open

    # Readiness cache
    READINESS_CACHE_TTL: int = 15      # seconds

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
