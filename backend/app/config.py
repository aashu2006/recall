"""App settings, read from env vars or the repo-root .env (see .env.example).

Use get_settings() everywhere, never os.environ directly, so tests can override it.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

    # Gnani (Prisma STT, Timbre TTS)
    gnani_api_key: str = ""
    gnani_stt_model: str = "prisma-v3.0"
    gnani_tts_model: str = "timbre-v2.5"
    gnani_tts_voice: str = "Poorvi"

    # WhatsApp Cloud API
    wa_token: str = ""
    wa_phone_number_id: str = ""
    wa_verify_token: str = ""
    wa_app_secret: str = ""
    wa_graph_api_version: str = "v21.0"
    wa_daily_send_cap: int = 50
    owner_wa_number: str = ""

    # LLMs (Groq primary, Gemini fallback)
    groq_api_key: str = ""
    groq_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_audio_bucket: str = "audio"


@lru_cache
def get_settings() -> Settings:
    return Settings()
