"""
Application configuration.

Reads settings from environment variables (and a .env file if present).
All values have sensible defaults so the app runs without any .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"

    # Database
    database_url: str = "sqlite+aiosqlite:///./bulk_cert.db"

    # File storage
    certificates_dir: str = "generated_certificates"

    # Batch limits
    max_batch_size: int = 500


# Single shared instance — import this everywhere.
settings = Settings()
