"""Settings from environment. Every provider is optional: without a key the app runs in demo mode."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
