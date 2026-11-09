import json
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "Studium-Notifications"
    environment: str = "Production"
    port: int = 8080
    host: str = "0.0.0.0"

    # AWS Configuration
    aws_region: str = "us-east-2"
    aws_endpoint_url: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # Amazon DynamoDB
    dynamodb_table_name: str = "studium_notifications"

    # Email / SES simulation
    simulate_ses_email: bool = True
    ses_sender_email: str = "notifications@studium.pucpr.br"

    # CORS Configuration
    cors_allowed_origins: str = "*"

    @property
    def parsed_cors_origins(self) -> list[str]:
        raw = self.cors_allowed_origins.strip()
        if not raw or raw == "*":
            return ["*"]
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(o).strip() for o in parsed if str(o).strip()]
            except Exception:
                pass
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
