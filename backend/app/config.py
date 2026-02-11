from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    anthropic_api_key: str
    motherduck_token: str
    motherduck_database: str = "KS2-Service Agent Read"
    claude_model: str = "claude-sonnet-4-5-20250929"
    row_limit: int = 500
    ollama_base_url: str = "http://localhost:11434"
    ollama_insight_model: str = "mistral"
    ollama_timeout: int = 120
    motherduck_logging_token: str = ""
    motherduck_logging_database: str = "munuiq"
    # Comma-separated list of additional schemas to expose (munu is always included)
    extra_schemas: str = "admin,cakeiteasy,planday,reference"
    # JWT auth
    jwt_secret_key: str = ""
    jwt_expire_minutes: int = 1440  # 24 hours
    # Superadmin seed (created on first startup)
    munuiq_admin_email: str = ""
    munuiq_admin_password: str = ""

    model_config = {"env_file": Path(__file__).resolve().parent.parent / ".env"}


settings = Settings()
