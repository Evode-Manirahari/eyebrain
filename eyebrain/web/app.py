"""eyebrain web UI — the demo surface.

Ask a natural-language question; the server retrieves the most relevant moments across
all cameras (fully local), synthesizes a cited answer with the on-device LLM, and returns
for each citation a thumbnail extracted live from the LOCAL source video at the cited
timecode. Raw video stays on the node — only the single requested frame is ever served."""

from __future__ import annotations

import io
import os

import cv2
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

from ..rag.retriever import make_retriever
from ..rag.synthesize import synthesize_cited_answer
from .registry import CameraRegistry
from .ui import INDEX_HTML

TOP_K = int(os.getenv("EYEBRAIN_WEB_TOP_K", "5"))

app = FastAPI(title="eyebrain")
_retriever = make_retriever()
_registry = CameraRegistry.load()


class AskRequest(BaseModel):
    question: str
    top_k: int | None = None


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return INDEX_HTML


@app.get("/api/cameras")
def cameras() -> JSONResponse:
    return JSONResponse(
        {
            "cameras": [c.model_dump() for c in _registry.cameras.values()],
            "indexed_moments": _retriever.count(),
            "retriever": getattr(_retriever, "name", "unknown"),
        }
    )


@app.post("/api/ask")
def ask(req: AskRequest) -> JSONResponse:
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "empty question")
    results = _retriever.search(question, top_k=req.top_k or TOP_K)
    answer = synthesize_cited_answer(question, results)

    citations = []
    for r in results:
        m = r.moment
        entry = _registry.get(m.camera_id)
        citations.append(
            {
                "camera_id": m.camera_id,
                "camera_name": m.camera_name or m.camera_id,
                "time_range": m.time_range,
                "start_sec": m.start_sec,
                "summary": m.summary,
                "score": round(r.score, 3),
                "thumb_url": (
                    f"/api/frame?camera={m.camera_id}&t={m.start_sec}" if entry else None
                ),
            }
        )
    return JSONResponse(
        {
            "question": question,
            "answer": answer.answer,
            "synthesis": answer.metadata.get("synthesis"),
            "citations": citations,
        }
    )


@app.get("/api/frame")
def frame(camera: str = Query(...), t: float = Query(0.0)) -> Response:
    """Extract a single JPEG from the local source video at time `t` (seconds)."""
    entry = _registry.get(camera)
    if entry is None:
        raise HTTPException(404, f"camera {camera} not registered")
    cap = cv2.VideoCapture(entry.video_path)
    if not cap.isOpened():
        raise HTTPException(500, f"cannot open source video for {camera}")
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000)
        ok, img = cap.read()
        if not ok:
            raise HTTPException(404, "frame not found at timecode")
        # overlay a small timecode badge
        cv2.putText(img, f"{camera}  t={t:.1f}s", (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(img, f"{camera}  t={t:.1f}s", (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise HTTPException(500, "failed to encode frame")
        return Response(content=io.BytesIO(buf.tobytes()).read(), media_type="image/jpeg")
    finally:
        cap.release()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("EYEBRAIN_WEB_PORT", "8000")))


if __name__ == "__main__":
    main()
