"""Add a camera from an existing video FILE (e.g. a higher-quality phone recording).

Same on-device pipeline as the webcam recorder, but for a file you already have:
copy into data/videos -> Qwen-VL caption (local) -> embed + index -> register.

Usage:
  python scripts/add_camera.py --video ~/Desktop/front.mov --camera-id cam1 --name "Front Display" --reset
  python scripts/add_camera.py --video ~/Desktop/hall.mov  --camera-id cam2 --name "Back Hallway"
Then:  make moss-sync   (push to Moss)   and restart the app:  make web

Any common format works (mov/mp4/avi); the web player transcodes to browser mp4 as needed.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from eyebrain.config import VIDEO_DIR
from eyebrain.embeddings import make_embedder
from eyebrain.index import MomentIndex
from eyebrain.ingest import ingest_video
from eyebrain.web.registry import CameraRegistry


def main() -> None:
    ap = argparse.ArgumentParser(description="Add a camera from a video file (on-device).")
    ap.add_argument("--video", required=True, help="Path to the source video file")
    ap.add_argument("--camera-id", required=True)
    ap.add_argument("--name", default=None, help="Human-friendly camera name")
    ap.add_argument("--sample-every", type=float, default=2.0, help="Seconds between sampled frames")
    ap.add_argument("--vision-model", default="qwen2.5vl:3b")
    ap.add_argument("--embedder", default="fastembed")
    ap.add_argument("--reset", action="store_true", help="Clear the index first (use on the first camera)")
    args = ap.parse_args()

    src = Path(args.video).expanduser()
    if not src.exists():
        print(f"ERROR: video not found: {src}", file=sys.stderr)
        sys.exit(1)

    dest = VIDEO_DIR / f"{args.camera_id}{src.suffix.lower()}"
    # Clear any prior recording for this camera (e.g. an old .avi) to avoid stale players.
    for old in VIDEO_DIR.glob(f"{args.camera_id}.*"):
        old.unlink()
    shutil.copy2(src, dest)
    print(f">>> copied {src.name} -> {dest}")

    reg = CameraRegistry.load()
    reg.register(args.camera_id, str(dest), args.name)
    reg.save()

    print(f">>> captioning with {args.vision_model} on-device (slow step)...")
    moments = ingest_video(
        video_path=dest,
        camera_id=args.camera_id,
        camera_name=args.name,
        sample_every_sec=args.sample_every,
        vision_model=args.vision_model,
    )
    index = MomentIndex(embedder=make_embedder(args.embedder))
    if args.reset:
        index.clear()
    index.add_moments(moments)
    print(f">>> indexed {len(moments)} moments for {args.camera_id}. Total: {len(index.load())}")
    print(">>> next:  make moss-sync   then restart:  make web")


if __name__ == "__main__":
    main()
