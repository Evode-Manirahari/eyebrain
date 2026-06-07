"""Generate two readable placeholder camera videos (H.264/avc1) so the web UI has real
frames to extract while we wait for real demo footage. Scene labels are burned in so the
extracted thumbnail visibly matches the cited timecode."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from eyebrain.config import VIDEO_DIR

FPS = 8
W, H = 640, 360
DUR = 60  # seconds

# (start_sec, end_sec, label) — loosely mirrors the caption sidecars
SCENES = {
    "cam1": [(0, 12, "front display: staff stocking shelf"),
             (12, 26, "front display: customer approaches"),
             (26, 60, "front display: product on floor")],
    "cam2": [(0, 30, "back hallway: quiet"),
             (30, 60, "back hallway: ladder + drill left by exit")],
}


def render(cam: str, scenes) -> Path:
    out = VIDEO_DIR / f"{cam}.mp4"
    vw = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"avc1"), FPS, (W, H))
    if not vw.isOpened():
        raise RuntimeError("avc1 writer failed to open")
    for f in range(DUR * FPS):
        t = f / FPS
        img = np.full((H, W, 3), 28, np.uint8)
        label = next((l for s, e, l in scenes if s <= t < e), "")
        cv2.rectangle(img, (0, 0), (W, 26), (50, 60, 70), -1)
        cv2.putText(img, f"{cam.upper()}  {t:5.1f}s", (10, 19),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)
        # moving subject so frames differ
        x = int(60 + (t * 9) % (W - 160))
        cv2.rectangle(img, (x, 180), (x + 70, 280), (0, 140, 255), -1)
        cv2.putText(img, label, (16, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (180, 230, 255), 1, cv2.LINE_AA)
        vw.write(img)
    vw.release()
    return out


if __name__ == "__main__":
    for cam, scenes in SCENES.items():
        p = render(cam, scenes)
        print(f"wrote {p}")
