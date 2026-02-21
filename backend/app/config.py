"""Application configuration."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings from environment."""

    database_url: str = "sqlite:///./affectlens.db"  # Use postgresql://... for production
    secret_key: str = "dev-secret-change-in-production"
    environment: str = "development"
    upload_dir: str = "uploads"
    max_upload_mb: int = 100

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
