from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_seconds(value: float) -> str:
    total = max(0, int(round(value)))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class Moment(BaseModel):
    """Compact camera-side observation safe to store in the central index."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    camera_id: str = Field(min_length=1)
    camera_name: str | None = None
    start_sec: float = Field(ge=0)
    end_sec: float = Field(ge=0)
    observed_at: datetime = Field(default_factory=utc_now)
    summary: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0, le=1)
    source_ref: str | None = None
    evidence: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_time_range(self) -> "Moment":
        if self.end_sec < self.start_sec:
            raise ValueError("end_sec must be greater than or equal to start_sec")
        return self

    @property
    def time_range(self) -> str:
        if self.start_sec == self.end_sec:
            return format_seconds(self.start_sec)
        return f"{format_seconds(self.start_sec)}-{format_seconds(self.end_sec)}"

    @property
    def display_camera(self) -> str:
        if self.camera_name:
            return f"{self.camera_name} ({self.camera_id})"
        return self.camera_id

    def searchable_text(self) -> str:
        parts = [
            self.camera_id,
            self.camera_name or "",
            self.summary,
            " ".join(self.tags),
        ]
        return " ".join(part for part in parts if part).strip()


class IndexedMoment(Moment):
    embedding: list[float]
    embedding_backend: str = "hash"


class QueryResult(BaseModel):
    moment: Moment
    score: float


class Citation(BaseModel):
    id: str
    camera_id: str
    camera_name: str | None = None
    time_range: str
    score: float
    summary: str

    @classmethod
    def from_result(cls, result: QueryResult) -> "Citation":
        return cls(
            id=result.moment.id,
            camera_id=result.moment.camera_id,
            camera_name=result.moment.camera_name,
            time_range=result.moment.time_range,
            score=result.score,
            summary=result.moment.summary,
        )


class CitedAnswer(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    metadata: dict[str, Any] = Field(default_factory=dict)

