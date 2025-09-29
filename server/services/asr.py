from __future__ import annotations

import asyncio
import io
import logging
import os
import subprocess
import wave
from functools import lru_cache
from typing import Optional

if os.getenv("KMP_DUPLICATE_LIB_OK") is None:
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
from faster_whisper import WhisperModel

from ..config import Settings


logger = logging.getLogger(__name__)


def decode_opus_to_wav_bytes(opus_bytes: bytes, ffmpeg_path: Optional[str]) -> bytes:
    """Use ffmpeg to decode Ogg/Opus bytes to mono 16kHz WAV bytes."""
    if not ffmpeg_path:
        raise RuntimeError("FFMPEG_PATH is not configured; cannot decode Opus audio")
    # ffmpeg -i pipe:0 -ar 16000 -ac 1 -f wav pipe:1
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-f",
        "wav",
        "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate(opus_bytes)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg decode failed: {err.decode('utf-8', 'ignore')}")
    return out


def wav_bytes_to_f32_mono(wav_bytes: bytes) -> np.ndarray:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        nch = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        fr = wf.getframerate()
        nframes = wf.getnframes()
        pcm = wf.readframes(nframes)
    if sampwidth != 2:
        raise ValueError("expected 16-bit PCM")
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if nch > 1:
        audio = audio.reshape(-1, nch).mean(axis=1)
    # If not 16k, we already forced 16k via ffmpeg
    return audio


@lru_cache(maxsize=4)
def _load_model(model_size: str, device: str) -> WhisperModel:
    compute_type = "float16" if device == "cuda" else "int8"
    return WhisperModel(model_size, device=device, compute_type=compute_type)


async def transcribe_opus(opus_bytes: bytes, settings: Settings) -> str:
    """Decode Opus and run faster-whisper transcription. Returns final text."""
    # Decode to WAV using ffmpeg (blocking, so run in thread)
    wav_bytes = await asyncio.to_thread(decode_opus_to_wav_bytes, opus_bytes, settings.__dict__.get("FFMPEG_PATH"))
    audio = wav_bytes_to_f32_mono(wav_bytes)

    desired = (getattr(settings, "WHISPER_DEVICE", "auto") or "auto").lower()
    if desired not in {"auto", "cuda", "cpu"}:
        logger.warning("Invalid WHISPER_DEVICE '%s'; falling back to auto", desired)
        desired = "auto"

    device_priority = ["cuda", "cpu"]
    if desired == "cpu":
        device_priority = ["cpu"]
    elif desired == "cuda":
        device_priority = ["cuda", "cpu"]

    model = None
    last_error: Optional[Exception] = None
    for device in device_priority:
        try:
            model = await asyncio.to_thread(_load_model, settings.ASR_MODEL, device)
            if device != desired and desired != "auto":
                logger.info("Whisper model loaded on %s after falling back from %s", device, desired)
            break
        except Exception as exc:
            last_error = exc
            logger.warning("Whisper model load failed on %s: %s", device, exc)
            continue

    if model is None:
        raise RuntimeError("Failed to load Whisper model") from last_error

    # Run transcription in a worker thread
    def _do_transcribe() -> str:
        segments, info = model.transcribe(
            audio,
            language=None,  # auto-detect
            beam_size=1,
            vad_filter=True,
        )
        text_parts = []
        for seg in segments:
            text_parts.append(seg.text)
        return " ".join(t.strip() for t in text_parts if t.strip())

    text = await asyncio.to_thread(_do_transcribe)
    return text or ""
