"""Settings from environment. Every provider is optional: without a key the app runs in demo mode."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
                                      extra="ignore")

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_vision_model: str = "gpt-4.1"
    openai_text_model: str = "gpt-4.1-mini"

    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_model: str = "bulbul:v3"
    sarvam_speaker: str = "kavya"
    sarvam_pace: float = 0.95

    soniox_api_key: str = ""
    soniox_base_url: str = "https://api.soniox.com"
    soniox_model: str = "stt-async-v5"

    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_graph_url: str = "https://graph.facebook.com/v21.0"

    data_dir: Path = BACKEND_DIR / "var"
    frontend_dist: Path = BACKEND_DIR.parent / "frontend" / "dist"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    request_timeout_s: float = 45.0
    max_upload_mb: int = 12

    # First admin, created at startup only when no admin exists yet. Change the password after first login.
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    # Demo servers only. When set, one sample login per role is kept with this password and the sign in page lists
    # the logins (never the password). Leave empty on any server that holds real consumers' bills.
    demo_accounts_password: str = ""
    session_hours: int = 12
    # Cookies ignore the port, so two instances on one host (dev and QA) need different names.
    session_cookie: str = "bm_session"
    cookie_secure: bool = False  # set true behind HTTPS
    whatsapp_complaint_template: str = ""  # approved template for replies outside the 24 hour window
    # Told to consumers when they complain, and the point after which the console marks a complaint overdue.
    complaint_reply_days: int = Field(default=7, ge=1)
    # The public Bill Mitra WhatsApp number, digits with country code, for the web "Raise on WhatsApp" link.
    whatsapp_display_number: str = Field(default="", pattern=r"^(\d{10,15})?$")

    # DPDP Act 2023: the notice version a consumer agreed to, who to ask, and how long bills are kept.
    privacy_notice_version: str = "2026-10-1"
    privacy_contact: str = ""
    retention_days: int = Field(default=180, ge=1)

    # DISCOM billing records for the evidence pack. Both empty means not connected, and nothing is fetched.
    billing_records_url: str = ""
    billing_records_token: str = ""

    # Automation (app/services/scheduler.py): reminders, lapses, overdue and escalation, digest, patterns.
    automation_enabled: bool = True
    automation_interval_seconds: int = Field(default=900, ge=60)
    reminder_after_days: int = Field(default=3, ge=1)
    lapse_after_days: int = Field(default=7, ge=1)
    digest_hour_ist: int = Field(default=8, ge=0, le=23)
    pattern_window_days: int = Field(default=90, ge=1)
    pattern_min_cases: int = Field(default=3, ge=2)

    # development (default) or production. In production the ownership check cannot be switched off.
    app_env: Literal["development", "production"] = "development"
    # Off only in development: bills by service number come from this database and nobody proves ownership.
    ownership_check: bool = True
    # Mixed into service number and mobile hashes, so a leaked table cannot be reversed by trying every number.
    hash_pepper: str = ""
    # DISCOM bill and registered mobile lookup by service number. Both empty means not connected.
    discom_bills_url: str = ""
    discom_bills_token: str = ""
    # Approved WhatsApp authentication template that carries a one-time code. Empty means codes cannot be sent.
    whatsapp_code_template: str = ""

    @model_validator(mode="after")
    def _production_keeps_ownership(self) -> "Settings":
        if self.app_env == "production" and not self.ownership_check:
            raise ValueError("OWNERSHIP_CHECK=false is refused when APP_ENV=production.")
        if self.app_env == "production" and not self.hash_pepper:
            raise ValueError("HASH_PEPPER must be set when APP_ENV=production.")
        return self

    @property
    def dev_bills(self) -> bool:
        """Development shortcut: stored bills stand in for the DISCOM and ownership is not checked."""
        return self.app_env == "development" and not self.ownership_check

    @property
    def discom_bills_live(self) -> bool:
        return bool(self.discom_bills_url and self.discom_bills_token)

    @property
    def vision_live(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def tts_live(self) -> bool:
        return bool(self.sarvam_api_key)

    @property
    def stt_live(self) -> bool:
        return bool(self.soniox_api_key)

    @property
    def billing_records_live(self) -> bool:
        return bool(self.billing_records_url and self.billing_records_token)

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_token and self.whatsapp_phone_number_id and self.whatsapp_verify_token)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "media").mkdir(exist_ok=True)
    return settings
