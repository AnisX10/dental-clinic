"""Application configuration.

Everything can be overridden with `CLINIC_`-prefixed environment variables or a
`backend/.env` file. Defaults are suited for a fully local, single-server
deployment (the dentist PC).
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / ".output" / "public"

# Product version: shown in Paramètres, surfaced by `cli.py version` and
# bumped on every release that reaches a customer machine.
APP_VERSION = "1.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BASE_DIR / ".env"),
        env_prefix="CLINIC_",
        extra="ignore",
    )

    app_name: str = "Cabinet Dentaire"
    # Empty => use the bundled local PostgreSQL (pgserver) stored under data/pgdata.
    database_url: str = ""
    data_dir: Path = PROJECT_ROOT / "data"
    attachments_dir: Path = PROJECT_ROOT / "data" / "attachments"
    backups_dir: Path = PROJECT_ROOT / "data" / "backups"

    # Session handling. Cookies are HttpOnly + SameSite=Lax; the app is plain HTTP on the LAN.
    session_ttl_hours: int = 12
    cookie_secure: bool = False

    # Login rate limiting: max attempts per window, per username+IP.
    login_max_attempts: int = 8
    login_window_seconds: int = 300

    # Backup defaults (editable in the settings UI, stored in clinic_settings).
    backup_hour: int = 20
    backup_keep_daily: int = 14
    backup_keep_manual: int = 5

    # Off-site copy target (second disk, USB autos-mount path, network share or
    # a cloud-sync folder). Empty disables it. Every successful backup is
    # mirrored there with the same retention counts.
    backup_offsite_dir: str = ""

    max_attachment_mb: int = 15

    # Extra CORS origins for development only. Production serves the SPA from
    # the same origin, so no CORS is needed; keep the attack surface at zero
    # unless explicitly widened for a dev setup via CLINIC_CORS_EXTRA_ORIGINS.
    cors_extra_origins: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
