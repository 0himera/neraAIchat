from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENROUTER_API_KEY: str | None = None
    JINA_API_KEY: str | None = None
    PIPER_PATH: str | None = None
    FFMPEG_PATH: str | None = None

    USE_FAISS_GPU: bool = False
    ASR_MODEL: str = "medium"
    SHORT_TERM_MESSAGES: int = 20

    MAX_PDF_MB: int = 50
    MAX_DOCS: int = 1000

    FRONTEND_ORIGIN: str = "http://localhost:5173"
    OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "x-ai/grok-4-fast:free"

    # TTS settings (Piper)
    TTS_VOICE_DEFAULT: str = "en"  # "en" or "ru"
    PIPER_VOICE_EN: str | None = None  # path to EN voice (e.g., .onnx/.json dir)
    PIPER_VOICE_RU: str | None = None  # path to RU voice

    # Jina AI models
    JINA_EMBEDDINGS_MODEL: str = "jina-embeddings-v4"  # placeholder; set v4 when available
    JINA_RERANKER_MODEL: str = "jina-reranker-m0"      # placeholder; set m0 when available
    JINA_EMBED_BATCH: int = 16

    # Always read the .env located next to this file (server/.env)
    _ENV_PATH = str(Path(__file__).resolve().parent / ".env")
    model_config = SettingsConfigDict(env_file=_ENV_PATH, env_file_encoding="utf-8")
