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
    gnani_base_url: str = "https://api.vachana.ai"
    gnani_stt_model: str = "prisma-v3.0"
    gnani_stt_language_code: str = "hi-IN,en-IN"
    gnani_stt_format: str = "codemix"
    # Fallback keyterms when transcribe() gets none. Per-client lists are built from the DB.
    gnani_stt_keyterms: list[str] = []
    gnani_stt_timeout: float = 60.0
    # VAD chunks sent to Prisma REST (limit 30 s). Lower it for finer proof clips.
    gnani_stt_max_chunk_s: float = 28.0
    gnani_tts_model: str = "timbre-v2.5"
    gnani_tts_voice: str = "Poorvi"

    # WhatsApp Cloud API
    wa_token: str = ""
    wa_phone_number_id: str = ""
    wa_verify_token: str = ""
    wa_app_secret: str = ""
    wa_graph_api_version: str = "v21.0"
    wa_graph_base_url: str = "https://graph.facebook.com"
    wa_daily_send_cap: int = 50
    owner_wa_number: str = ""

    # LLMs (Groq primary, Gemini fallback)
    groq_api_key: str = ""
    groq_model: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    gemini_api_key: str = ""
    gemini_model: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    llm_timeout: float = 30.0

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_audio_bucket: str = "audio"


@lru_cache
def get_settings() -> Settings:
    return Settings()
