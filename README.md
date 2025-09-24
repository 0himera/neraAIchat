# NeraAIchat

Local voice chat with RAG, LLM, and TTS

## Stack
- Backend: FastAPI (Python 3.11), WebSocket + REST
- ASR: faster-whisper (GPU if available)
- TTS: Piper (local binary)
- LLM: OpenRouter API (sonoma-sky-alpha), streamed
- RAG: PyMuPDF + Jina Embeddings v4 + FAISS (CPU by default, GPU optional) + Jina Reranker m0
- Storage: JSON (ORJSON), local folders under `server/data/`
- Frontend: React 18 + Vite + Redux, WebSocket streaming, dark theme

## Prerequisites 
- Python 3.11
- Node.js 18+
- CUDA 12.3 (installed) for GPU inference
- FFmpeg (optional, recommended) for Ogg/Opus decode on server: https://www.gyan.dev/ffmpeg/builds/
- Piper TTS binary and voices (EN/optional RU). You can download from https://github.com/rhasspy/piper/releases

## Environment
Create `server/.env` based on `server/.env.example`:
```
OPENROUTER_API_KEY=sk-or-...
JINA_API_KEY=jina-...
PIPER_PATH=C:\\tools\\piper\\piper.exe
USE_FAISS_GPU=false
ASR_MODEL=medium
SHORT_TERM_MESSAGES=20
MAX_PDF_MB=50
MAX_DOCS=1000
```

## Install (Backend)
From project root:
```
# Create and activate venv (optional)
python -m venv .venv
.\.venv\Scripts\activate

# Install deps
pip install -r server/requirements.txt
```

Run backend:
```
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

## Install (Frontend)
From project root:
```
cd client
npm install
npm run dev
```
The dev server runs on http://localhost:5173 and connects to backend ws/rest on http://localhost:8000

## Notes on FAISS GPU (Windows)
- Official `faiss-gpu` wheels for Windows are limited. For GPU you may prefer conda installation.
- This project defaults to FAISS CPU and provides an adapter. If you install FAISS GPU separately, set `USE_FAISS_GPU=true` and ensure imports succeed.

## Roadmap
- Implement streaming ASR (faster-whisper) with partial + final transcripts
- Proxy OpenRouter streaming to client via WebSocket
- Piper streaming TTS over WebSocket (Ogg/Opus 48kHz)
- PDF ingestion + RAG (embeddings via Jina, local FAISS, reranker)
- Session JSON memory with ORJSON and periodic flush

## Dev tips
- If FFmpeg is not installed yet, use PCM/WAV during early development.
- Keep API keys only in `server/.env`. Frontend never sees them.
