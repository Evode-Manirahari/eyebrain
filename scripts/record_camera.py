"""Record a staged clip from the Mac webcam and run the FULL on-device pipeline on it:
record -> Qwen-VL caption (local) -> embed + index (local) -> register camera.

One command per "camera". Point the webcam at a scene, act out an incident, and eyebrain
indexes it. Raw video is saved locally (data/videos) and never leaves the node.

Usage:
  python scripts/record_camera.py --camera-id cam1 --name "Front Display" --seconds 30 --reset
  python scripts/record_camera.py --camera-id cam2 --name "Back Hallway"  --seconds 30

Then open the web UI:  python -m eyebrain.web.app   (or:  make web)

Notes:
- opencv-python-headless has no preview window; watch your webcam light and the terminal
  countdown. Grant Camera permission to your terminal app on first run
  (System Settings -> Privacy & Security -> Camera).
"""

from __future__ import annotations

import argparse
import sys
import time

import cv2

from eyebrain.config import VIDEO_DIR
from eyebrain.embeddings import make_embedder
from eyebrain.index import MomentIndex
from eyebrain.ingest import ingest_video
from eyebrain.web.registry import CameraRegistry


def record(camera_id: str, seconds: float, device: int) -> str:
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        print(
            f"ERROR: could not open webcam (device {device}). Grant Camera permission to "
            "your terminal in System Settings -> Privacy & Security -> Camera, then retry.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Warm up / read real frame size.
    for _ in range(5):
        cap.read()
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    fps = 20.0  # webcams lie about fps; pin a sane value for the writer

    # AVFoundation's H.264 writer is picky about resolution; try a few codecs/containers.
    vw = None
    out_path = None
    for fourcc, ext in [("avc1", ".mp4"), ("mp4v", ".mp4"), ("MJPG", ".avi")]:
        p = str(VIDEO_DIR / f"{camera_id}{ext}")
        cand = cv2.VideoWriter(p, cv2.VideoWriter_fourcc(*fourcc), fps, (w, h))
        if cand.isOpened():
            vw, out_path = cand, p
            print(f">>> writer: {fourcc} -> {p}")
            break
        cand.release()
    if vw is None:
        print("ERROR: no working video writer (avc1/mp4v/MJPG all failed).", file=sys.stderr)
        sys.exit(1)

    print(f"\n>>> Recording {camera_id} for {seconds:.0f}s at {w}x{h}. Get ready...")
    for n in (3, 2, 1):
        print(f"    {n}...", flush=True)
        time.sleep(1)
    print("    ACTION! (act out the scene)\n", flush=True)

    start = time.time()
    last_tick = -1
    frames = 0
    while True:
        elapsed = time.time() - start
        if elapsed >= seconds:
            break
        ok, frame = cap.read()
        if not ok:
            break
        vw.write(frame)
        frames += 1
        tick = int(elapsed)
        if tick != last_tick:
            print(f"    rec {tick:>2}/{int(seconds)}s", end="\r", flush=True)
            last_tick = tick

    cap.release()
    vw.release()
    print(f"\n>>> Saved {frames} frames -> {out_path}")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Record + on-device index one camera.")
    ap.add_argument("--camera-id", required=True)
    ap.add_argument("--name", default=None, help="Human-friendly camera name")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--device", type=int, default=0, help="Webcam device index")
    ap.add_argument("--sample-every", type=float, default=2.0)
    ap.add_argument("--vision-model", default="qwen2.5vl:3b")
    ap.add_argument("--embedder", default="fastembed")
    ap.add_argument("--reset", action="store_true", help="Clear the index first (use on the first camera)")
    args = ap.parse_args()

    video_path = record(args.camera_id, args.seconds, args.device)

    # Register so the web UI can pull frames from this local video.
    reg = CameraRegistry.load()
    reg.register(args.camera_id, video_path, args.name)
    reg.save()

    print(f">>> Captioning with {args.vision_model} on-device (this is the slow step)...")
    moments = ingest_video(
        video_path=video_path,
        camera_id=args.camera_id,
        camera_name=args.name,
        sample_every_sec=args.sample_every,
        vision_model=args.vision_model,
    )
    index = MomentIndex(embedder=make_embedder(args.embedder))
    if args.reset:
        index.clear()
    index.add_moments(moments)
    print(f">>> Indexed {len(moments)} moments for {args.camera_id}. Total in index: {len(index.load())}")
    print(">>> Done. Launch the UI with:  python -m eyebrain.web.app")


if __name__ == "__main__":
    main()
