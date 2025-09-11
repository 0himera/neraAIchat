from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..config import Settings
from ..services.llm import stream_chat
from ..services.asr import transcribe_opus
from ..services.tts import synthesize_ogg_opus, synthesize_wav
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/asr")
async def ws_asr(ws: WebSocket):
    await ws.accept()
    settings = Settings()
    total_bytes = 0
    buffer = bytearray()
    try:
        # Receive Opus chunks and on 'final' run transcription
        while True:
            try:
                msg = await ws.receive()
            except RuntimeError:
                # Happens if client disconnects abruptly; exit loop quietly
                logger.info("/ws/asr receive after disconnect; ending")
                break
            if "bytes" in msg and msg["bytes"] is not None:
                chunk = msg["bytes"]
                total_bytes += len(chunk)
                buffer.extend(chunk)
                # Partial indicator (byte count)
                await ws.send_json({"type": "partial", "text": f"audio: {total_bytes} bytes"})
            elif "text" in msg and msg["text"] is not None:
                data = (msg["text"] or "").strip().lower()
                if data == "final":
                    try:
                        logger.info("/ws/asr final: total_bytes=%d, ffmpeg=%s, model=%s", total_bytes, getattr(settings, "FFMPEG_PATH", None), settings.ASR_MODEL)
                        opus_blob = bytes(buffer)
                        buffer.clear()
                        text = await transcribe_opus(opus_blob, settings)
                        await ws.send_json({"type": "final", "text": text})
                        total_bytes = 0
                    except Exception as e:
                        logger.exception("/ws/asr error during transcription: %s", e)
                        await ws.send_json({"type": "error", "message": str(e)})
            else:
                # Ignore other message types
                pass
    except WebSocketDisconnect:
        # Client disconnected
        logger.info("/ws/asr disconnect")
        return


@router.websocket("/ws/llm")
async def ws_llm(ws: WebSocket):
    await ws.accept()
    settings = Settings()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"text": raw}

            user_text = (payload.get("text") or "").strip()
            if not user_text:
                await ws.send_json({"type": "error", "message": "empty input"})
                continue

            # Stream tokens from OpenRouter via our proxy service
            try:
                logger.info("/ws/llm streaming start: model=%s url=%s", settings.LLM_MODEL, settings.OPENROUTER_API_URL)
                async for token in stream_chat(user_text, settings):
                    if token:
                        await ws.send_json({"type": "token", "text": token})
                await ws.send_json({"type": "done"})
            except Exception as e:
                # Fallback: simple echo to avoid total failure
                logger.exception("/ws/llm streaming failed, falling back to echo: %s", e)
                await ws.send_json({"type": "token", "text": user_text})
                await ws.send_json({"type": "done"})
    except WebSocketDisconnect:
        logger.info("/ws/llm disconnect")
        return


@router.websocket("/ws/tts")
async def ws_tts(ws: WebSocket):
    await ws.accept()
    settings = Settings()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"text": raw}

            text = (payload.get("text") or "").strip()
            voice = (payload.get("voice") or settings.TTS_VOICE_DEFAULT).strip().lower()
            if not text:
                await ws.send_json({"type": "error", "message": "empty text"})
                continue

            # TEMP: force WAV-only to guarantee audible playback while we stabilize ffmpeg/Opus
            logger.info("/ws/tts synth start (WAV-only): voice=%s path_piper=%s voice_en=%s voice_ru=%s", voice, settings.PIPER_PATH, getattr(settings, "PIPER_VOICE_EN", None), getattr(settings, "PIPER_VOICE_RU", None))
            try:
                await ws.send_json({"type": "start", "codec": "audio/wav"})
                wav_bytes = await asyncio.to_thread(synthesize_wav, text, settings, voice)
                size = len(wav_bytes) if wav_bytes else 0
                logger.info("/ws/tts wav bytes=%d", size)
                if size <= 0:
                    raise RuntimeError("wav payload empty")
                await ws.send_bytes(wav_bytes)
                await ws.send_json({"type": "end", "bytes": size})
            except Exception as e2:
                logger.exception("/ws/tts wav failed: %s", e2)
                await ws.send_json({"type": "error", "message": f"tts failed: {e2}"})
    except WebSocketDisconnect:
        logger.info("/ws/tts disconnect")
        return
