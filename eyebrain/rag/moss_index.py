"""Moss-backed retrieval — the sponsor (Moss) semantic-search runtime as eyebrain's
'central node'.

Cameras caption frames locally with Qwen-VL; only the compact text moment (summary +
camera + timecode metadata) is sent to Moss. Raw video never leaves the node. Moss does
the sub-10ms hybrid (semantic + keyword) retrieval across all cameras; Qwen then
synthesizes the cited answer on top. This mirrors eyebrain's stated architecture exactly.

Drop-in compatible with `eyebrain.index.MomentIndex`: exposes `search(question, top_k)
-> list[QueryResult]`, `add_moments(...)`, `count()`, and `clear()`. The local fastembed
`MomentIndex` remains the offline/no-key fallback (see `rag.retriever.make_retriever`).

STATUS: requires MOSS_PROJECT_ID / MOSS_PROJECT_KEY (free at portal.usemoss.dev).
The Moss SDK is async; we wrap it behind the sync interface the web/voice layers use.
Not exercised in CI — verify once keys are available.
"""

from __future__ import annotations

import asyncio
import os

from ..models import Moment, QueryResult

_DEFAULT_INDEX = os.getenv("EYEBRAIN_MOSS_INDEX", "eyebrain")
# alpha: 1.0 = pure semantic, 0.0 = pure keyword. 0.7 blends both (good for proper nouns
# like "red jacket" plus semantic paraphrase like "knocked over" ~ "bumped / fell").
_DEFAULT_ALPHA = float(os.getenv("EYEBRAIN_MOSS_ALPHA", "0.7"))


def _run(coro):
    """Run an async Moss call from sync code. FastAPI runs sync endpoints in a worker
    thread, so a fresh event loop here is safe."""
    return asyncio.run(coro)


class MossIndex:
    def __init__(
        self,
        index_name: str = _DEFAULT_INDEX,
        project_id: str | None = None,
        project_key: str | None = None,
    ) -> None:
        self.index_name = index_name
        self._project_id = project_id or os.getenv("MOSS_PROJECT_ID")
        self._project_key = project_key or os.getenv("MOSS_PROJECT_KEY")
        if not (self._project_id and self._project_key):
            raise RuntimeError(
                "Moss credentials missing. Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY "
                "(free at portal.usemoss.dev)."
            )
        self._loaded = False

    def _client(self):
        from moss import MossClient

        return MossClient(self._project_id, self._project_key)

    @staticmethod
    def _to_document(m: Moment):
        from moss import DocumentInfo

        return DocumentInfo(
            id=m.id,
            text=m.searchable_text(),
            metadata={
                "camera_id": m.camera_id,
                "camera_name": m.camera_name or "",
                "start_sec": m.start_sec,
                "end_sec": m.end_sec,
                "summary": m.summary,
                "tags": ",".join(m.tags),
                "confidence": m.confidence,
            },
        )

    @staticmethod
    def _to_moment(doc) -> Moment:
        md = doc.metadata or {}
        return Moment(
            id=doc.id,
            camera_id=md.get("camera_id", "unknown"),
            camera_name=md.get("camera_name") or None,
            start_sec=float(md.get("start_sec", 0.0)),
            end_sec=float(md.get("end_sec", md.get("start_sec", 0.0))),
            summary=md.get("summary") or doc.text,
            tags=[t for t in (md.get("tags") or "").split(",") if t],
            confidence=float(md.get("confidence", 0.75)),
        )

    # --- mutation ---
    async def _ensure_index(self, client, initial_docs: list | None = None) -> None:
        existing = {ix.name for ix in await client.list_indexes()}
        if self.index_name not in existing:
            await client.create_index(self.index_name, initial_docs or [], "moss-minilm")

    def add_moments(self, moments: list[Moment]) -> int:
        if not moments:
            return 0
        docs = [self._to_document(m) for m in moments]

        async def _add():
            client = self._client()
            existing = {ix.name for ix in await client.list_indexes()}
            if self.index_name not in existing:
                await client.create_index(self.index_name, docs, "moss-minilm")
            else:
                await client.add_docs(self.index_name, docs)
            return len(docs)

        return _run(_add())

    def clear(self) -> None:
        async def _clear():
            client = self._client()
            existing = {ix.name for ix in await client.list_indexes()}
            if self.index_name in existing:
                await client.delete_index(self.index_name)

        _run(_clear())
        self._loaded = False

    # --- query ---
    def search(self, question: str, top_k: int = 5) -> list[QueryResult]:
        from moss import QueryOptions

        async def _q():
            client = self._client()
            await client.load_index(self.index_name)
            res = await client.query(
                self.index_name, question, QueryOptions(top_k=top_k, alpha=_DEFAULT_ALPHA)
            )
            return res.docs

        docs = _run(_q())
        return [QueryResult(moment=self._to_moment(d), score=float(d.score)) for d in docs]

    def count(self) -> int:
        async def _c():
            client = self._client()
            try:
                ix = await client.get_index(self.index_name)
                return int(getattr(ix, "document_count", 0) or 0)
            except Exception:
                return 0

        return _run(_c())
