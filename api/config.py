"""Application settings, loaded from environment (see /etc/solarx-api.env at deploy)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # Read-only database access for the API
    solarx_ro_db_user: str = "solarx_ro"
    solarx_ro_db_password: str = ""
    solarx_db: str = "solarx"
    db_host: str = "localhost"

    # Auth
    dash_username: str = "hantaro88"
    dash_password_hash: str = ""  # argon2 hash; never store plaintext
    jwt_secret: str = ""
    jwt_ttl_hours: int = 12

    # Login brute-force protection
    login_max_attempts: int = 5
    login_window_minutes: int = 15


def get_settings() -> Settings:
    return Settings()
