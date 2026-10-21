import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Application Info
    APP_NAME: str = "Secure Remote Device Access & Live Screen Monitoring"
    APP_ENV: str = "production"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "prod-super-secret-key-change-in-production-min-32-chars-long!")
    
    # Database
    # Defaults to local SQLite file for zero-dependency instant startup,
    # or connects to PostgreSQL when DATABASE_URL is set (e.g. postgresql://user:pass@localhost:5432/remote_support)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite:///./remote_support.db"
    )

    # JWT Settings
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours for admin sessions
    ALGORITHM: str = "HS256"

    # Coturn / WebRTC ICE Configuration
    STUN_SERVER: str = os.getenv("STUN_SERVER", "stun:stun.l.google.com:19302")
    TURN_SERVER: str = os.getenv("TURN_SERVER", "") # e.g. "turn:turn.support.local:3478"
    TURN_SECRET: str = os.getenv("TURN_SECRET", "coturn-secure-hmac-auth-secret-key")
    TURN_CREDENTIAL_TTL_SECONDS: int = 3600

    # Invitation & Session Defaults
    INVITATION_TTL_MINUTES: int = 15
    MAX_SESSION_DURATION_MINUTES: int = 120
    DEFAULT_PERMITTED_ACTIONS: List[str] = ["screen_view", "live_pointer", "chat"]

    # Security & Rate Limiting
    CORS_ORIGINS: List[str] = ["*"]
    ALLOW_CREDENTIALS: bool = True
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

