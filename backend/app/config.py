from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # This will automatically load variables from .env file
    # You don't need to manually load them
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(...)
    jwt_secret: str = Field(...)
    jwt_algorithm: str = Field("HS256")
    jwt_expires_minutes: int = Field(1440)
    # Store raw comma-separated string; parsed via computed_field below
    # so pydantic-settings never tries to JSON-decode it.
    cors_origins_raw: str = Field("http://localhost:5173", alias="cors_origins")

    llm_model: str = Field("openai/gpt-4o-mini")
    openai_api_key: str = Field("")
    vampi_base_url: str = Field("http://localhost:5001")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        # You'll have URLs like http://localhost:5173;http://[IP_ADDRESS]
        # Split by ',' and strip whitespace
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
