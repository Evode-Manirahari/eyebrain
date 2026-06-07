"""Browser-playable video for the clip player.

Recordings may be MJPG/.avi (the webcam H.264 fallback), which browsers can't play.
We transcode each source to a cached H.264 .mp4 (file-to-file avc1 works even when the
live-capture writer didn't) and serve it with HTTP Range support so the <video> element
can seek straight to a cited timecode."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")
_CHUNK = 1 << 20  # 1 MiB


def ensure_web_mp4(src_path: str) -> Path:
    """Return a browser-playable .mp4 for `src_path`, transcoding+caching if needed."""
    src = Path(src_path)
    if not src.exists():
        raise HTTPException(404, f"source video missing: {src_path}")
    if src.suffix.lower() == ".mp4":
        return src

    out = src.with_suffix(".web.mp4")
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out

    try:
        import cv2
    except ImportError as exc:
        raise HTTPException(503, "OpenCV is required to transcode non-mp4 footage; install eyebrain[vision]") from exc

    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise HTTPException(500, f"cannot open {src}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"avc1")  # type: ignore[attr-defined]
    vw = cv2.VideoWriter(str(out), fourcc, fps, (w, h))
    if not vw.isOpened():
        cap.release()
        raise HTTPException(500, "avc1 transcode writer failed to open")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        vw.write(frame)
    cap.release()
    vw.release()
    return out


def serve_with_range(path: Path, range_header: str | None) -> Response:
    """Serve `path` as video/mp4, honoring a single Range request (206) for seeking."""
    size = path.stat().st_size
    if not range_header:
        return StreamingResponse(
            _file_iter(path, 0, size - 1),
            media_type="video/mp4",
            headers={"Accept-Ranges": "bytes", "Content-Length": str(size)},
        )

    m = _RANGE_RE.search(range_header)
    start = int(m.group(1)) if m and m.group(1) else 0
    end = int(m.group(2)) if m and m.group(2) else size - 1
    end = min(end, size - 1)
    if start > end:
        raise HTTPException(416, "invalid range")
    length = end - start + 1
    return StreamingResponse(
        _file_iter(path, start, end),
        status_code=206,
        media_type="video/mp4",
        headers={
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        },
    )


def _file_iter(path: Path, start: int, end: int):
    with open(path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = f.read(min(_CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
