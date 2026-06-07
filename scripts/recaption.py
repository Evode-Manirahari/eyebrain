"""Re-caption all registered cameras with a chosen vision model (no re-recording).
Reads each camera's existing local video from the registry, re-runs the VLM, and rebuilds
the local index. Usage: python scripts/recaption.py [model]  (default qwen2.5vl:7b)."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("EYEBRAIN_EMBEDDER", "fastembed")

from eyebrain.embeddings import make_embedder  # noqa: E402
from eyebrain.index import MomentIndex  # noqa: E402
from eyebrain.ingest import ingest_video  # noqa: E402
from eyebrain.web.registry import CameraRegistry  # noqa: E402

model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5vl:7b"
reg = CameraRegistry.load()
if not reg.cameras:
    print("No cameras registered.")
    raise SystemExit(1)

index = MomentIndex(embedder=make_embedder("fastembed"))
index.clear()
for cam_id, entry in reg.cameras.items():
    print(f">>> re-captioning {entry.camera_name or cam_id} with {model} …", flush=True)
    moments = ingest_video(
        video_path=entry.video_path, camera_id=cam_id, camera_name=entry.camera_name,
        sample_every_sec=2.0, vision_model=model,
    )
    index.add_moments(moments)
    print(f"    {len(moments)} moments", flush=True)
print(f">>> done. total moments: {len(index.load())}")
