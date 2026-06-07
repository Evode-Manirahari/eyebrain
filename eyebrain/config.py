"""Central configuration. Everything is overridable via environment variables so the
same code runs on a laptop (demo) or an edge node (production)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("EYEBRAIN_DATA_DIR", ROOT / "data"))
VIDEO_DIR = DATA_DIR / "videos"
FRAME_DIR = DATA_DIR / "frames"
INDEX_DIR = DATA_DIR / "index"

for _d in (VIDEO_DIR, FRAME_DIR, INDEX_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- Local models (on-device via Ollama) ---
OLLAMA_HOST = os.getenv("EYEBRAIN_OLLAMA_HOST", "http://localhost:11434")
VLM_MODEL = os.getenv("EYEBRAIN_VLM_MODEL", "qwen2.5vl:3b")
LLM_MODEL = os.getenv("EYEBRAIN_LLM_MODEL", "qwen2.5:3b")
EMBED_MODEL = os.getenv("EYEBRAIN_EMBED_MODEL", "BAAI/bge-small-en-v1.5")

# --- Ingestion knobs ---
# Sample at most one frame every N seconds, plus scene-change keyframes.
SAMPLE_EVERY_SECONDS = float(os.getenv("EYEBRAIN_SAMPLE_EVERY_SECONDS", "2.0"))
# Scene-change sensitivity: mean abs frame diff above this (0-255) forces a keyframe.
SCENE_CHANGE_THRESHOLD = float(os.getenv("EYEBRAIN_SCENE_CHANGE_THRESHOLD", "12.0"))
# Resize long edge to this before sending to the VLM (speed on CPU).
FRAME_MAX_EDGE = int(os.getenv("EYEBRAIN_FRAME_MAX_EDGE", "768"))

# --- Retrieval knobs ---
TOP_K = int(os.getenv("EYEBRAIN_TOP_K", "6"))
