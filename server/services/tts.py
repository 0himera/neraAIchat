from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple
import io
import wave
import tempfile
import json
from threading import Lock

from ..config import Settings

# Cached Piper voices when using the Python API
_PIPER_VOICE_CACHE: dict[str, object] = {}
_PIPER_VOICE_LOCKS: dict[str, Lock] = {}


def _resolve_voice_paths(voice_path: str) -> Tuple[str, Optional[str]]:
    """Return (model_path, config_path) for Piper.
    Accepts either a direct .onnx file path, or a directory containing *.onnx and *.onnx.json
    """
    vp = Path(voice_path)
    if vp.is_dir():
        # pick first .onnx in directory
        onnx_files = sorted(vp.glob("*.onnx"))
        if not onnx_files:
            raise RuntimeError(f"No .onnx model found in directory: {voice_path}")
        model = onnx_files[0]
        cfg = Path(str(model) + ".json")
        return str(model), (str(cfg) if cfg.exists() else None)
    else:
        model = vp
        if not model.exists():
            raise RuntimeError(f"Voice model not found: {voice_path}")
        cfg = Path(str(model) + ".json")
        return str(model), (str(cfg) if cfg.exists() else None)


def _run_piper_cli(text: str, piper_path: str, voice_path: str, speed: Optional[float] = None) -> bytes:
    """Run Piper CLI to synthesize WAV into a temporary file and return its bytes.
    Uses --text with UTF-8 stdin (newline-terminated) for reliability on Windows.
    """
    if not piper_path or not voice_path:
        raise RuntimeError("Piper binary or voice path not configured")
    model_path, config_path = _resolve_voice_paths(voice_path)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        out_path = td_path / "piper_out.wav"

        errors: list[str] = []

        def try_variant(args: list[str]) -> Optional[bytes]:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=td_path)
            out, er = proc.communicate((text + "\n").encode('utf-8'))
            if proc.returncode != 0:
                msg = er.decode('utf-8', 'ignore')
                errors.append(f"code={proc.returncode} stderr={msg[:200]} cmd={' '.join(args)}")
                return None
            # wait for file to appear/grow a bit
            for _ in range(20):
                try:
                    if out_path.exists() and out_path.stat().st_size > 44:
                        break
                except Exception:
                    pass
                time.sleep(0.02)
            if out_path.exists() and out_path.stat().st_size > 44:
                data = out_path.read_bytes()
                if len(data) < 100 and out and len(out) > len(data):
                    return out
                return data
            # stdout fallback
            if out and len(out) > 100:
                return out
            return None

        base = [str(Path(piper_path).resolve()), '--model', str(Path(model_path).resolve())]
        if config_path:
            base += ['-c', str(Path(config_path).resolve())]
        if speed and speed > 0:
            length_scale = max(0.25, min(4.0, round(1.0 / speed, 3)))
            base += ['--length_scale', str(length_scale)]

        # Variant 1: --output_file + --text
        cmd1 = base + ['--output_file', str(out_path.resolve()), '--text']
        result = try_variant(cmd1)
        if result:
            return result

        # Variant 2: -f wav -o + --text
        cmd2 = base + ['-f', 'wav', '-o', str(out_path.resolve()), '--text']
        result = try_variant(cmd2)
        if result:
            return result

        # Give up with detailed errors
        raise RuntimeError("piper failed to produce audio; tried variants:\n" + "\n".join(errors))


def _get_piper_voice(model_path: str):
    """Load and cache PiperVoice for a given model path. Returns (voice, lock)."""
    try:
        from piper.voice import PiperVoice  # type: ignore
    except Exception as e:
        raise ImportError(f"piper-tts not installed or not importable: {e}")

    voice = _PIPER_VOICE_CACHE.get(model_path)
    if voice is None:
        voice = PiperVoice.load(model_path)
        _PIPER_VOICE_CACHE[model_path] = voice
        _PIPER_VOICE_LOCKS[model_path] = Lock()
    lock = _PIPER_VOICE_LOCKS[model_path]
    return voice, lock


def _run_piper_python(text: str, voice_path: str, speed: Optional[float] = None) -> bytes:
    """Use Piper Python API to synthesize WAV into memory and return its bytes."""
    model_path, _ = _resolve_voice_paths(voice_path)
    voice, lock = _get_piper_voice(model_path)
    buf = io.BytesIO()
    # Piper's synthesize writes a proper WAV header/frames to an open wave file
    with lock:
        with wave.open(buf, "wb") as wf:
            kwargs = {}
            if speed and speed > 0:
                kwargs['length_scale'] = max(0.25, min(4.0, 1.0 / speed))
            # PiperVoice.synthesize will configure WAV params and write frames
            voice.synthesize(text, wf, **kwargs)  # type: ignore[attr-defined]
    return buf.getvalue()


def _run_piper(text: str, piper_path: str, voice_path: str, speed: Optional[float] = None) -> bytes:
    """Try Piper Python API first (fast, stable), then fall back to CLI."""
    try:
        return _run_piper_python(text, voice_path, speed=speed)
    except Exception:
        # Fall back to CLI path
        return _run_piper_cli(text, piper_path, voice_path, speed=speed)


def _wav_to_ogg_opus(wav_bytes: bytes, ffmpeg_path: str) -> bytes:
    if not ffmpeg_path:
        raise RuntimeError("FFMPEG_PATH not configured")
    # If provided path doesn't exist, try using 'ffmpeg' from PATH as a fallback
    ff = ffmpeg_path
    try:
        if not Path(ff).is_file():
            ff = "ffmpeg"
    except Exception:
        ff = "ffmpeg"
    # Encode to Ogg/Opus 48kHz mono
    cmd = [
        ff,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "wav",
        "-i",
        "pipe:0",
        "-ar",
        "48000",
        "-ac",
        "1",
        "-c:a",
        "libopus",
        "-frame_duration",
        "20",
        "-application",
        "voip",
        "-f",
        "ogg",
        "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate(wav_bytes)
    if proc.returncode != 0:
        msg = err.decode('utf-8', 'ignore')
        if not msg:
            msg = f"ffmpeg encode failed (empty stderr). Tried ffmpeg binary: {ff}"
        raise RuntimeError(msg)
    return out


def _pcm_to_ogg_opus(pcm_bytes: bytes, ffmpeg_path: str, sr_candidates: tuple[int, ...] = (22050, 24000, 22500)) -> bytes:
    if not ffmpeg_path:
        raise RuntimeError("FFMPEG_PATH not configured")
    ff = ffmpeg_path
    try:
        if not Path(ff).is_file():
            ff = "ffmpeg"
    except Exception:
        ff = "ffmpeg"

    last_err = None
    for sr in sr_candidates:
        cmd = [
            ff,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "s16le",
            "-ar",
            str(sr),
            "-ac",
            "1",
            "-i",
            "pipe:0",
            "-ar",
            "48000",
            "-ac",
            "1",
            "-c:a",
            "libopus",
            "-frame_duration",
            "20",
            "-application",
            "voip",
            "-f",
            "ogg",
            "pipe:1",
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(pcm_bytes)
        if proc.returncode == 0 and out:
            return out
        last_err = err.decode('utf-8', 'ignore')
    msg = last_err or "ffmpeg encode failed for raw PCM (empty stderr)."
    raise RuntimeError(msg)


def synthesize_ogg_opus(text: str, settings: Settings, voice: Optional[str] = None, speed: Optional[float] = None) -> bytes:
    voice_code = (voice or settings.TTS_VOICE_DEFAULT or "en").lower()
    if voice_code == "ru":
        voice_path = settings.PIPER_VOICE_RU or settings.PIPER_VOICE_EN
    else:
        voice_path = settings.PIPER_VOICE_EN or settings.PIPER_VOICE_RU

    wav_or_pcm = _run_piper(text, settings.PIPER_PATH or "piper", voice_path, speed=speed)
    # Detect WAV header (RIFF .... WAVE)
    is_wav = len(wav_or_pcm) >= 12 and wav_or_pcm.startswith(b"RIFF") and (wav_or_pcm[8:12] == b"WAVE")
    if is_wav:
        try:
            ogg = _wav_to_ogg_opus(wav_or_pcm, settings.FFMPEG_PATH or "ffmpeg")
        except Exception:
            # If wav path fails for any reason, try as raw PCM
            ogg = _pcm_to_ogg_opus(wav_or_pcm, settings.FFMPEG_PATH or "ffmpeg")
    else:
        # Treat as raw PCM s16le and try common sample rates
        ogg = _pcm_to_ogg_opus(wav_or_pcm, settings.FFMPEG_PATH or "ffmpeg")
    return ogg


def synthesize_wav(text: str, settings: Settings, voice: Optional[str] = None, speed: Optional[float] = None) -> bytes:
    """Directly synthesize WAV using Piper (no ffmpeg required).
    If Piper output is raw PCM, wrap it into a WAV container so browsers can play it.
    """
    voice_code = (voice or settings.TTS_VOICE_DEFAULT or "en").lower()
    if voice_code == "ru":
        voice_path = settings.PIPER_VOICE_RU or settings.PIPER_VOICE_EN
    else:
        voice_path = settings.PIPER_VOICE_EN or settings.PIPER_VOICE_RU
    data = _run_piper(text, settings.PIPER_PATH or "piper", voice_path, speed=speed)
    # If it's already WAV, return as-is
    if len(data) >= 12 and data.startswith(b"RIFF") and (data[8:12] == b"WAVE"):
        return data
    # Otherwise, assume raw PCM s16le mono and wrap with WAV header (try common sample rates)
    for sr in (22050, 24000, 22500, 16000):
        try:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # s16le
                wf.setframerate(sr)
                wf.writeframes(data)
            return buf.getvalue()
        except Exception:
            continue
    # fallback last resort
    return data
