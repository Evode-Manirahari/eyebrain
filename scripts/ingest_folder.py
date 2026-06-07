"""Batch-ingest a folder of clips — each video becomes a camera. For a demo that feels
like a real always-on system with lots of footage: film many short scenario clips
(parking lot, checkout, front door, hallway…), drop them in one folder, run this once.

Every video is captioned on-device with Qwen-VL, indexed, and registered (so thumbnails
+ the clip player work). Camera id/name come from the filename.

Usage:
  python scripts/ingest_folder.py ~/Desktop/clips --reset
  make moss-sync && make web

Filename -> camera:  "front_desk.mov" -> id "front_desk", name "Front Desk".
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

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest every video in a folder as a camera (on-device).")
    ap.add_argument("folder", help="Folder containing video clips")
    ap.add_argument("--sample-every", type=float, default=2.0)
    ap.add_argument("--vision-model", default="qwen2.5vl:3b")
    ap.add_argument("--embedder", default="fastembed")
    ap.add_argument("--reset", action="store_true", help="Clear index + registry first")
    args = ap.parse_args()

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"ERROR: not a folder: {folder}", file=sys.stderr)
        sys.exit(1)
    videos = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXTS)
    if not videos:
        print(f"ERROR: no videos ({', '.join(sorted(VIDEO_EXTS))}) in {folder}", file=sys.stderr)
        sys.exit(1)

    index = MomentIndex(embedder=make_embedder(args.embedder))
    registry = CameraRegistry.load()
    if args.reset:
        index.clear()
        registry = CameraRegistry()

    total = 0
    for i, src in enumerate(videos, 1):
        cam_id = src.stem.lower().replace(" ", "_").replace("-", "_")
        name = src.stem.replace("_", " ").replace("-", " ").title()
        dest = VIDEO_DIR / f"{cam_id}{src.suffix.lower()}"
        for old in VIDEO_DIR.glob(f"{cam_id}.*"):
            old.unlink()
        shutil.copy2(src, dest)
        registry.register(cam_id, str(dest), name)
        registry.save()
        print(f">>> [{i}/{len(videos)}] {name}: captioning on-device with {args.vision_model}…")
        moments = ingest_video(
            video_path=dest, camera_id=cam_id, camera_name=name,
            sample_every_sec=args.sample_every, vision_model=args.vision_model,
        )
        index.add_moments(moments)
        total += len(moments)
        print(f"    indexed {len(moments)} moments")

    print(f">>> Done: {len(videos)} cameras, {total} moments. Next:  make moss-sync  then  make web")


if __name__ == "__main__":
    main()
