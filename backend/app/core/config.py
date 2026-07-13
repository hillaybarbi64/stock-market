"""Application configuration.

All secrets come exclusively from environment variables / the local .env file.
Nothing here holds a real credential; see .env.example for the full list.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ibkr-dashboard"
    app_version: str = "0.1.0"
    environment: str = "local"  # local | server
    log_level: str = "INFO"
    log_format: str = "console"  # console | json

    # API server — bound to localhost only by default (see SECURITY.md)
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    database_url: str = "postgresql+asyncpg://ibkr:ibkr@localhost:5432/ibkr_dashboard"

    # IB Gateway (live, read-only). 4001 = live, 4002 = paper; this system targets live.
    ibkr_gateway_host: str = "127.0.0.1"
    ibkr_gateway_port: int = 4001
    ibkr_client_id: int = 17  # arbitrary but stable client id for this app
    ibkr_readonly: bool = True  # hard default; the connection layer refuses False in this build
    ibkr_reconnect_max_interval_s: int = 300

    # Flex Web Service (historical, read-only by nature)
    ibkr_flex_token: str = ""  # secret — env only, masked in logs
    ibkr_flex_query_id: str = ""

    # Intraday snapshot cadence (minutes); 0 disables
    snapshot_interval_min: int = 15

    # Display defaults (user-adjustable later via settings table)
    default_timezone: str = "Asia/Jerusalem"
    base_currency_fallback: str = "USD"

    data_dir: str = "./data"  # uploads/attachments; git-ignored


@lru_cache
def get_settings() -> Settings:
    return Settings()
