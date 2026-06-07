from __future__ import annotations

import base64
from typing import Any

from .models import Moment


class HeuristicVisionSummarizer:
    """Fallback summarizer when no local vision model is configured."""

    def summarize(
        self,
        *,
        camera_id: str,
        camera_name: str | None,
        timestamp_sec: float,
        duration_sec: float,
        brightness: float | None = None,
        motion_score: float | None = None,
        source_ref: str | None = None,
    ) -> Moment:
        tags: list[str] = []
        description = "local camera observation"
        if motion_score is not None:
            if motion_score > 0.18:
                tags.append("high-motion")
                description = "high motion detected"
            elif motion_score > 0.06:
                tags.append("motion")
                description = "motion detected"
            else:
                tags.append("still")
                description = "low motion scene"
        if brightness is not None:
            tags.append("bright" if brightness > 0.65 else "dark" if brightness < 0.25 else "normal-light")

        summary = f"{description} at {camera_name or camera_id} around {timestamp_sec:.1f}s."
        return Moment(
            camera_id=camera_id,
            camera_name=camera_name,
            start_sec=timestamp_sec,
            end_sec=timestamp_sec + duration_sec,
            summary=summary,
            tags=tags,
            confidence=0.35,
            source_ref=source_ref,
            evidence={
                "motion_score": round(motion_score, 4) if motion_score is not None else None,
                "brightness": round(brightness, 4) if brightness is not None else None,
            },
        )


class OllamaVisionSummarizer:
    """Local vision adapter for models served by Ollama."""

    def __init__(self, model: str) -> None:
        import ollama

        self.model = model
        self.client = ollama

    def summarize_frame(
        self,
        *,
        frame_jpeg: bytes,
        camera_id: str,
        camera_name: str | None,
        timestamp_sec: float,
        duration_sec: float,
        source_ref: str | None = None,
    ) -> Moment:
        prompt = (
            "You are describing security camera footage for a private local index. "
            "Return one concise sentence about visible actions, objects, location, and anomalies. "
            "Do not infer identity or sensitive attributes."
        )
        response = self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64.b64encode(frame_jpeg).decode("ascii")],
                }
            ],
        )
        summary = _extract_ollama_content(response)
        return Moment(
            camera_id=camera_id,
            camera_name=camera_name,
            start_sec=timestamp_sec,
            end_sec=timestamp_sec + duration_sec,
            summary=summary,
            tags=["vision-model"],
            confidence=0.8,
            source_ref=source_ref,
        )


def _extract_ollama_content(response: Any) -> str:
    if isinstance(response, dict):
        message = response.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    message = getattr(response, "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    return "Local vision model returned an empty observation."

