from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..config import Settings
from ..services.llm import stream_chat
from ..services.rag import rag_engine
from ..services.sessions import sessions_manager
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

    async def safe_send_json(payload: dict[str, Any]) -> bool:
        try:
            await ws.send_json(payload)
            return True
        except WebSocketDisconnect:
            logger.info("/ws/llm client disconnected during send")
            return False
        except RuntimeError as exc:
            logger.debug("/ws/llm failed to send payload due to runtime error: %s", exc)
            return False

    try:
        while True:
            try:
                raw = await ws.receive_text()
            except WebSocketDisconnect:
                logger.info("/ws/llm disconnect during receive")
                break
            except RuntimeError as exc:
                logger.debug("/ws/llm receive failed due to runtime error: %s", exc)
                break
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"text": raw}

            user_text = (payload.get("text") or "").strip()
            session_id = (payload.get("session_id") or "").strip()
            user_message_id = (payload.get("message_id") or "").strip() or None
            assistant_message_id = (payload.get("assistant_id") or "").strip() or None
            system_prompt = (payload.get("system_prompt") or "").strip()
            memory_notes = (payload.get("memory_notes") or "").strip()
            if len(system_prompt) > 4000:
                system_prompt = system_prompt[:4000]
            if len(memory_notes) > 4000:
                memory_notes = memory_notes[:4000]
            if not user_text:
                await ws.send_json({"type": "error", "message": "empty input"})
                continue

            if not session_id:
                await ws.send_json({"type": "error", "message": "session_id required"})
                continue

            try:
                await sessions_manager.ensure_session(session_id)
            except ValueError:
                await ws.send_json({"type": "error", "message": "session not found"})
                continue

            try:
                user_record = {"role": "user", "text": user_text}
                if user_message_id:
                    user_record["id"] = user_message_id
                if system_prompt:
                    user_record["system_prompt"] = system_prompt
                if memory_notes:
                    user_record["memory_notes"] = memory_notes
                append_result = await sessions_manager.append_message(session_id, user_record)
                await ws.send_json({"type": "session_update", "session": append_result["session"], "message": append_result["message"]})
            except Exception as e:
                logger.exception("/ws/llm failed to persist user message: %s", e)
                await ws.send_json({"type": "error", "message": "failed to store message"})
                continue

            context_chunks = []
            try:
                await rag_engine.ensure_initialized(settings)
                context_chunks = await rag_engine.query(user_text, settings, top_k=5)
            except Exception as e:
                logger.exception("/ws/llm RAG retrieval failed: %s", e)
                context_chunks = []

            # Stream tokens from OpenRouter via our proxy service
            try:
                logger.info("/ws/llm streaming start: model=%s url=%s", settings.LLM_MODEL, settings.OPENROUTER_API_URL)
                assistant_reply = ""
                stream_ok = True
                async for token in stream_chat(
                    user_text,
                    settings,
                    context_chunks=context_chunks,
                    system_prompt=system_prompt or None,
                    memory_notes=memory_notes or None,
                ):
                    if token:
                        assistant_reply += token
                        if not await safe_send_json({"type": "token", "text": token}):
                            stream_ok = False
                            break
                if stream_ok:
                    stream_ok = await safe_send_json({"type": "done"})
                if stream_ok and assistant_reply.strip():
                    try:
                        append_result = await sessions_manager.append_message(
                            session_id,
                            {"role": "assistant", "text": assistant_reply, "id": assistant_message_id}
                            if assistant_message_id
                            else {"role": "assistant", "text": assistant_reply},
                        )
                        await safe_send_json({"type": "session_update", "session": append_result["session"], "message": append_result["message"]})
                    except Exception as e:
                        logger.exception("/ws/llm failed to persist assistant message: %s", e)
            except Exception as e:
                # Fallback: simple echo to avoid total failure
                logger.exception("/ws/llm streaming failed, falling back to echo: %s", e)
                if await safe_send_json({"type": "token", "text": user_text}):
                    await safe_send_json({"type": "done"})
                try:
                    append_result = await sessions_manager.append_message(
                        session_id,
                        {"role": "assistant", "text": user_text, "id": assistant_message_id}
                        if assistant_message_id
                        else {"role": "assistant", "text": user_text},
                    )
                    await safe_send_json({"type": "session_update", "session": append_result["session"], "message": append_result["message"]})
                except Exception as e2:
                    logger.exception("/ws/llm fallback persist failed: %s", e2)
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
            speed = payload.get("speed")
            if not text:
                await ws.send_json({"type": "error", "message": "empty text"})
                continue

            # TEMP: force WAV-only to guarantee audible playback while we stabilize ffmpeg/Opus
            logger.info("/ws/tts synth start (WAV-only): voice=%s path_piper=%s voice_en=%s voice_ru=%s", voice, settings.PIPER_PATH, getattr(settings, "PIPER_VOICE_EN", None), getattr(settings, "PIPER_VOICE_RU", None))
            try:
                await ws.send_json({"type": "start", "codec": "audio/wav"})
                wav_bytes = await asyncio.to_thread(synthesize_wav, text, settings, voice, speed)
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
