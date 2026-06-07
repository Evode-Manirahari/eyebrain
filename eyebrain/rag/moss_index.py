"""Moss-backed retrieval via the Linux sidecar (sponsor: Moss semantic-search runtime).

The Moss native runtime has no macOS x86_64 wheel, so it runs in a Linux container
(see moss_sidecar/) and we talk to it over loopback HTTP. This module is the Mac-side
client: it maps Moments to/from Moss documents and forwards add/query/clear to the
sidecar. Credentials (MOSS_PROJECT_ID/KEY) live in the sidecar's env, not here.

eyebrain's pitch, made literal: cameras caption frames locally with Qwen-VL; only the
compact text moment (summary + camera/timecode metadata) goes to Moss. Raw video never
leaves the node. Moss does sub-10ms hybrid retrieval across all cameras; Qwen synthesizes
the cited answer on top.

Drop-in compatible with MomentIndex: search / add_moments / count / clear.
Activate with EYEBRAIN_RETRIEVER=moss (see rag.retriever). STATUS: requires the sidecar
running (make moss-up) with valid Moss creds; not exercised in CI."""

from __future__ import annotations

import os

import requests

from ..models import Moment, QueryResult

_DEFAULT_URL = os.getenv("MOSS_SIDECAR_URL", "http://127.0.0.1:8077")
_DEFAULT_ALPHA = float(os.getenv("EYEBRAIN_MOSS_ALPHA", "0.7"))  # 1=semantic, 0=keyword


class MossIndex:
    name = "moss"

    def __init__(self, sidecar_url: str | None = None, timeout: float = 30.0) -> None:
        self.url = (sidecar_url or _DEFAULT_URL).rstrip("/")
        self.timeout = timeout
        # Fail fast if the sidecar isn't up, so the retriever factory falls back to local.
        r = requests.get(f"{self.url}/health", timeout=3)
        r.raise_for_status()

    @staticmethod
    def _to_doc(m: Moment) -> dict:
        # Moss metadata values must all be strings; _to_moment parses numerics back.
        return {
            "id": m.id,
            "text": m.searchable_text(),
            "metadata": {
                "camera_id": m.camera_id,
                "camera_name": m.camera_name or "",
                "start_sec": str(m.start_sec),
                "end_sec": str(m.end_sec),
                "summary": m.summary,
                "tags": ",".join(m.tags),
                "confidence": str(m.confidence),
            },
        }

    @staticmethod
    def _to_moment(doc: dict) -> Moment:
        md = doc.get("metadata") or {}
        start = float(md.get("start_sec", 0.0))
        return Moment(
            id=str(doc.get("id") or ""),
            camera_id=md.get("camera_id", "unknown"),
            camera_name=md.get("camera_name") or None,
            start_sec=start,
            end_sec=float(md.get("end_sec", start)),
            summary=md.get("summary") or doc.get("text", ""),
            tags=[t for t in (md.get("tags") or "").split(",") if t],
            confidence=float(md.get("confidence", 0.75)),
        )

    def add_moments(self, moments: list[Moment]) -> int:
        if not moments:
            return 0
        docs = [self._to_doc(m) for m in moments]
        r = requests.post(f"{self.url}/add", json={"docs": docs}, timeout=self.timeout)
        r.raise_for_status()
        return int(r.json().get("added", 0))

    def clear(self) -> None:
        requests.post(f"{self.url}/clear", timeout=self.timeout).raise_for_status()

    def search(self, question: str, top_k: int = 5) -> list[QueryResult]:
        r = requests.post(
            f"{self.url}/query",
            json={"text": question, "top_k": top_k, "alpha": _DEFAULT_ALPHA},
            timeout=self.timeout,
        )
        r.raise_for_status()
        docs = r.json().get("docs", [])
        return [QueryResult(moment=self._to_moment(d), score=float(d.get("score", 0.0))) for d in docs]

    def count(self) -> int:
        try:
            r = requests.get(f"{self.url}/count", timeout=5)
            return int(r.json().get("count", 0))
        except Exception:
            return 0
