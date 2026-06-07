from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from .embeddings import Embedder, cosine_similarity, make_embedder
from .models import IndexedMoment, Moment, QueryResult


class MomentIndex:
    def __init__(self, index_dir: Path | str = "data/index", embedder: Embedder | None = None) -> None:
        self.index_dir = Path(index_dir)
        self.path = self.index_dir / "moments.jsonl"
        self.embedder = embedder or make_embedder()

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def load(self) -> list[IndexedMoment]:
        if not self.path.exists():
            return []
        moments: list[IndexedMoment] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                moments.append(IndexedMoment.model_validate_json(line))
            except Exception as exc:  # pragma: no cover - protects long-running demo indexes.
                raise ValueError(f"invalid index record at {self.path}:{line_number}") from exc
        return moments

    def add_moments(self, moments: Iterable[Moment]) -> list[IndexedMoment]:
        incoming = list(moments)
        if not incoming:
            return []

        embeddings = self.embedder.encode([moment.searchable_text() for moment in incoming])
        indexed = [
            IndexedMoment(
                **moment.model_dump(),
                embedding=embedding,
                embedding_backend=self.embedder.name,
            )
            for moment, embedding in zip(incoming, embeddings)
        ]

        existing = {moment.id: moment for moment in self.load()}
        for moment in indexed:
            existing[moment.id] = moment

        self._write(existing.values())
        return indexed

    def search(self, question: str, top_k: int = 5, min_score: float | None = None) -> list[QueryResult]:
        indexed_moments = self.load()
        if not indexed_moments:
            return []

        if min_score is None:
            min_score = float(os.getenv("EYEBRAIN_MIN_SCORE", "0.12"))
        query_embedding = self.embedder.encode([question])[0]
        embeddings = self._compatible_embeddings(indexed_moments, len(query_embedding))
        results: list[QueryResult] = []
        for indexed, embedding in zip(indexed_moments, embeddings):
            score = cosine_similarity(query_embedding, embedding)
            if score < min_score:
                continue
            moment = Moment.model_validate(indexed.model_dump(exclude={"embedding", "embedding_backend"}))
            results.append(QueryResult(moment=moment, score=score))
        results.sort(key=lambda result: result.score, reverse=True)
        return results[:top_k]

    def _compatible_embeddings(self, moments: list[IndexedMoment], dimension: int) -> list[list[float]]:
        stale_indexes = [
            index
            for index, moment in enumerate(moments)
            if moment.embedding_backend != self.embedder.name or len(moment.embedding) != dimension
        ]
        if not stale_indexes:
            return [moment.embedding for moment in moments]

        embeddings = [moment.embedding for moment in moments]
        refreshed = self.embedder.encode([moments[index].searchable_text() for index in stale_indexes])
        for index, embedding in zip(stale_indexes, refreshed):
            embeddings[index] = embedding
        return embeddings

    def _write(self, moments: Iterable[IndexedMoment]) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps(moment.model_dump(mode="json"), sort_keys=True)
            for moment in sorted(moments, key=lambda item: (item.camera_id, item.start_sec, item.id))
        ]
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
