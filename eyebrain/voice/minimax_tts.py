"""MiniMax text-to-speech (sponsor). Used to speak eyebrain's cited answers in the web
demo — no LiveKit required. The intl T2A v2 endpoint authenticates with just the API key
(no Group ID) and returns hex-encoded MP3 in data.audio.

Configurable via env: MINIMAX_API_KEY (required), MINIMAX_TTS_BASE_URL, MINIMAX_TTS_MODEL,
MINIMAX_TTS_VOICE."""

from __future__ import annotations

import binascii
import os

import requests

DEFAULT_BASE_URL = os.getenv("MINIMAX_TTS_BASE_URL", "https://api.minimax.io/v1")
DEFAULT_MODEL = os.getenv("MINIMAX_TTS_MODEL", "speech-02-turbo")
DEFAULT_VOICE = os.getenv("MINIMAX_TTS_VOICE", "English_Trustworth_Man")


class MiniMaxTTSError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(os.getenv("MINIMAX_API_KEY"))


def synthesize(
    text: str,
    *,
    voice: str | None = None,
    model: str | None = None,
    speed: float = 1.0,
    timeout: float = 30.0,
) -> bytes:
    """Return MP3 bytes for `text`. Raises MiniMaxTTSError on failure."""
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        raise MiniMaxTTSError("MINIMAX_API_KEY not set")

    resp = requests.post(
        f"{DEFAULT_BASE_URL}/t2a_v2",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model or DEFAULT_MODEL,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice or DEFAULT_VOICE,
                "speed": speed,
                "vol": 1,
                "pitch": 0,
            },
            "audio_setting": {"sample_rate": 32000, "format": "mp3", "channel": 1},
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise MiniMaxTTSError(f"MiniMax HTTP {resp.status_code}: {resp.text[:200]}")

    body = resp.json()
    status = (body.get("base_resp") or {}).get("status_code", -1)
    if status != 0:
        raise MiniMaxTTSError(f"MiniMax error: {body.get('base_resp')}")

    audio_hex = (body.get("data") or {}).get("audio")
    if not audio_hex:
        raise MiniMaxTTSError("MiniMax returned no audio")
    return binascii.unhexlify(audio_hex)
