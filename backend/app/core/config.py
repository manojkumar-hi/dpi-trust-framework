from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DPI Trust Framework API"
    app_version: str = "0.1.0"
    database_url: str
    fabric_adapter_url: str = "http://localhost:8081"
    fabric_adapter_timeout_seconds: float = 10.0

    # Module 13 Authentication Settings
    auth_jwt_issuer: str = "https://auth.dpi-trust.local"
    auth_jwt_audience: str = "dpi-trust-framework"
    auth_jwks_url: str | None = None
    auth_static_public_key: str | None = None  # For dev/test
    auth_static_private_key: str | None = None # For issuing tokens
    auth_clock_skew_seconds: int = 60

    # Module 15.4 Verifier Identity
    verifier_did: str = "did:web:trust.dpi.local"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
