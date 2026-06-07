from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from eyebrain.models import Moment
from eyebrain.vision import HeuristicVisionSummarizer, OllamaVisionSummarizer


class CaptionRecord(BaseModel):
    time_sec: float = Field(ge=0)
    end_sec: float | None = Field(default=None, ge=0)
    summary: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.9, ge=0, le=1)


def load_caption_sidecar(path: Path | str) -> list[CaptionRecord]:
    caption_path = Path(path)
    records: list[CaptionRecord] = []
    for line_number, line in enumerate(caption_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        raw = json.loads(line)
        normalized = {
            "time_sec": raw.get("time_sec", raw.get("timestamp_sec", raw.get("time", raw.get("start_sec")))),
            "end_sec": raw.get("end_sec"),
            "summary": raw.get("summary", raw.get("caption", raw.get("text"))),
            "tags": raw.get("tags", []),
            "confidence": raw.get("confidence", 0.9),
        }
        try:
            records.append(CaptionRecord.model_validate(normalized))
        except Exception as exc:
            raise ValueError(f"invalid caption record at {caption_path}:{line_number}") from exc
    return records


def ingest_video(
    *,
    video_path: Path | str,
    camera_id: str,
    camera_name: str | None = None,
    sample_every_sec: float = 2.0,
    captions_path: Path | str | None = None,
    vision_model: str | None = None,
) -> list[Moment]:
    video = Path(video_path)
    source_ref = _source_ref(video)

    if captions_path is not None:
        return _moments_from_captions(
            captions=load_caption_sidecar(captions_path),
            camera_id=camera_id,
            camera_name=camera_name,
            default_duration=sample_every_sec,
            source_ref=source_ref,
        )

    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python-headless is required to ingest raw video without captions") from exc

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {video}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_sec = frame_count / fps if frame_count else 0
    summarizer = OllamaVisionSummarizer(vision_model) if vision_model else HeuristicVisionSummarizer()
    moments: list[Moment] = []
    previous_gray: Any | None = None
    timestamp = 0.0

    while timestamp <= duration_sec:
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, frame = cap.read()
        if not ok:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(cv2.mean(gray)[0]) / 255.0
        motion_score = None
        if previous_gray is not None:
            diff = cv2.absdiff(previous_gray, gray)
            motion_score = float(cv2.mean(diff)[0]) / 255.0
        previous_gray = gray

        if vision_model:
            ok, buffer = cv2.imencode(".jpg", frame)
            if not ok:
                raise RuntimeError("failed to encode sampled frame for local vision model")
            moment = summarizer.summarize_frame(
                frame_jpeg=buffer.tobytes(),
                camera_id=camera_id,
                camera_name=camera_name,
                timestamp_sec=timestamp,
                duration_sec=sample_every_sec,
                source_ref=source_ref,
            )
        else:
            moment = summarizer.summarize(
                camera_id=camera_id,
                camera_name=camera_name,
                timestamp_sec=timestamp,
                duration_sec=sample_every_sec,
                brightness=brightness,
                motion_score=motion_score,
                source_ref=source_ref,
            )
        moments.append(moment)
        timestamp += sample_every_sec

    cap.release()
    return moments


def _moments_from_captions(
    *,
    captions: list[CaptionRecord],
    camera_id: str,
    camera_name: str | None,
    default_duration: float,
    source_ref: str | None,
) -> list[Moment]:
    moments: list[Moment] = []
    for caption in captions:
        end_sec = caption.end_sec if caption.end_sec is not None else caption.time_sec + default_duration
        moments.append(
            Moment(
                camera_id=camera_id,
                camera_name=camera_name,
                start_sec=caption.time_sec,
                end_sec=end_sec,
                summary=caption.summary,
                tags=caption.tags,
                confidence=caption.confidence,
                source_ref=source_ref,
            )
        )
    return moments


def _source_ref(video_path: Path) -> str:
    try:
        stat = video_path.stat()
        payload = f"{video_path.name}:{stat.st_size}:{int(stat.st_mtime)}"
    except FileNotFoundError:
        payload = video_path.name
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

