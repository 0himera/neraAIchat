from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
import logging

from .config import Settings
from .routers import upload, ws, rag, sessions
from .services.rag import rag_engine


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
(DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "sessions").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "index").mkdir(parents=True, exist_ok=True)


settings = Settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="NeraAIchat API", default_response_class=ORJSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(rag.router, prefix="/api/rag", tags=["rag"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(ws.router, tags=["ws"])


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "asr_model": settings.ASR_MODEL,
        "use_faiss_gpu": settings.USE_FAISS_GPU,
        "short_term_messages": settings.SHORT_TERM_MESSAGES,
        "max_pdf_mb": settings.MAX_PDF_MB,
        "max_docs": settings.MAX_DOCS,
    }


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("API startup: data_dir=%s", str(DATA_DIR))
    logger.info(
        "Settings: FRONTEND_ORIGIN=%s, ASR_MODEL=%s, USE_FAISS_GPU=%s, OPENROUTER_URL=%s, LLM_MODEL=%s",
        settings.FRONTEND_ORIGIN,
        settings.ASR_MODEL,
        settings.USE_FAISS_GPU,
        settings.OPENROUTER_API_URL,
        settings.LLM_MODEL,
    )
    logger.info(
        "Paths: PIPER_PATH=%s, FFMPEG_PATH=%s, PIPER_VOICE_EN=%s, PIPER_VOICE_RU=%s",
        settings.PIPER_PATH,
        getattr(settings, "FFMPEG_PATH", None),
        getattr(settings, "PIPER_VOICE_EN", None),
        getattr(settings, "PIPER_VOICE_RU", None),
    )
    await rag_engine.initialize(settings)
