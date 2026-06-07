"""Camera registry: maps a camera_id to its human name and the LOCAL source video.

The compact index (moments + embeddings) deliberately does not contain video paths —
that's the privacy design. The registry is a node-local file that lets the UI pull a
single frame at a cited timecode for display. It never leaves the node and is not part
of the shareable index."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .. import config


class CameraEntry(BaseModel):
    camera_id: str
    camera_name: str | None = None
    video_path: str


class CameraRegistry(BaseModel):
    cameras: dict[str, CameraEntry] = {}

    @classmethod
    def path(cls, index_dir: str | Path | None = None) -> Path:
        return Path(index_dir or config.INDEX_DIR) / "cameras.json"

    @classmethod
    def load(cls, index_dir: str | Path | None = None) -> "CameraRegistry":
        p = cls.path(index_dir)
        if not p.exists():
            return cls()
        return cls.model_validate_json(p.read_text())

    def save(self, index_dir: str | Path | None = None) -> None:
        p = self.path(index_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2))

    def register(self, camera_id: str, video_path: str, camera_name: str | None = None) -> None:
        self.cameras[camera_id] = CameraEntry(
            camera_id=camera_id, camera_name=camera_name, video_path=str(video_path)
        )

    def get(self, camera_id: str) -> CameraEntry | None:
        return self.cameras.get(camera_id)
