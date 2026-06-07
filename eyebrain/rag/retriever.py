"""Retriever factory: choose the Moss runtime (sponsor, on-device-capable) or the local
local store (offline fallback). Both expose `search(question, top_k) -> list[QueryResult]`
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

    name = "local"

    def __init__(self) -> None:
        embedder_name = os.getenv("EYEBRAIN_EMBEDDER", "hash")
        self.name = f"local-{embedder_name}"
        self._index = MomentIndex(embedder=make_embedder(embedder_name))

    def search(self, question: str, top_k: int = 5) -> list[QueryResult]:
        return self._index.search(question, top_k=top_k)

    def count(self) -> int:
        return len(self._index.load())


class ResilientRetriever:
    """Try Moss first (sponsor runtime); fall back to the local on-device index on ANY
    error or empty result. Keeps the demo alive through Moss hiccups (e.g. a 503) with
    zero perceived failure — both paths are sub-300ms."""

    name = "moss+local-fallback"

    def __init__(self, primary, fallback: "LocalRetriever") -> None:
        self.primary = primary
        self.fallback = fallback

    def search(self, question: str, top_k: int = 5) -> list[QueryResult]:
        try:
            res = self.primary.search(question, top_k=top_k)
            if res:
                return res
        except Exception as exc:
            print(f"[eyebrain] Moss query failed ({exc}); using local fallback.", file=sys.stderr)
        return self.fallback.search(question, top_k=top_k)

    def count(self) -> int:
        try:
            n = self.primary.count()
            if n:
                return n
        except Exception:
            pass
        return self.fallback.count()


def make_retriever():
    backend = os.getenv("EYEBRAIN_RETRIEVER", "local").lower()
    if backend == "moss":
        try:
            from .moss_index import MossIndex

            return ResilientRetriever(MossIndex(), LocalRetriever())
        except Exception as exc:  # sidecar down / missing creds -> pure local
            print(f"[eyebrain] Moss unavailable ({exc}); using local retriever.", file=sys.stderr)
    return LocalRetriever()
