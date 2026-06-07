"""Retriever factory: choose the Moss runtime (sponsor, on-device-capable) or the local
fastembed store (offline fallback). Both expose `search(question, top_k) -> list[QueryResult]`
and `count() -> int`, so the web and voice layers don't care which is active.

Select with EYEBRAIN_RETRIEVER=moss|local (default: local). Moss requires MOSS_PROJECT_ID /
MOSS_PROJECT_KEY; if they're missing or the SDK isn't installed, we log and fall back to
local so the demo never hard-fails."""

from __future__ import annotations

import os
import sys

from ..embeddings import make_embedder
from ..index import MomentIndex
from ..models import QueryResult


class LocalRetriever:
    """Adapter over Codex's MomentIndex giving the common retriever interface."""

    name = "local-fastembed"

    def __init__(self) -> None:
        self._index = MomentIndex(embedder=make_embedder(os.getenv("EYEBRAIN_EMBEDDER", "fastembed")))

    def search(self, question: str, top_k: int = 5) -> list[QueryResult]:
        return self._index.search(question, top_k=top_k)

    def count(self) -> int:
        return len(self._index.load())


def make_retriever():
    backend = os.getenv("EYEBRAIN_RETRIEVER", "local").lower()
    if backend == "moss":
        try:
            from .moss_index import MossIndex

            r = MossIndex()
            r.name = "moss"  # type: ignore[attr-defined]
            return r
        except Exception as exc:  # missing keys / SDK -> graceful fallback
            print(f"[eyebrain] Moss retriever unavailable ({exc}); falling back to local.", file=sys.stderr)
    return LocalRetriever()
