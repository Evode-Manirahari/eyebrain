"""Moss sidecar — a thin HTTP proxy around the Moss Python SDK.

The Moss native runtime ships no macOS x86_64 wheel, so on an Intel Mac we run this
inside a Linux x86_64 container (where the wheel exists) and let the main eyebrain app
(eyebrain.rag.moss_index.MossIndex) call it over loopback HTTP. The proxy is deliberately
dumb: it forwards {id, text, metadata} docs and {text, top_k, alpha} queries straight to
Moss. All Moment<->doc mapping stays on the app side.

Env: MOSS_PROJECT_ID, MOSS_PROJECT_KEY, MOSS_INDEX (default "eyebrain")."""

from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI, HTTPException
from moss import DocumentInfo, MossClient, QueryOptions
from pydantic import BaseModel, Field


async def _retry(make_coro, tries: int = 5, base: float = 0.4):
    """Retry a Moss call through transient 5xx/timeout (the free-tier backend 503s
    intermittently). Re-raises non-transient errors immediately."""
    if tries < 1:
        raise ValueError("tries must be at least 1")
    last = None
    for i in range(tries):
        try:
            return await make_coro()
        except Exception as exc:  # noqa: BLE001
            last = exc
            s = str(exc).lower()
            if any(code in s for code in ("503", "502", "504", "timeout", "temporarily")):
                await asyncio.sleep(base * (i + 1))
                continue
            raise
    assert last is not None
    raise last

INDEX = os.getenv("MOSS_INDEX", "eyebrain")
MODEL = os.getenv("MOSS_MODEL", "moss-minilm")

app = FastAPI(title="moss-sidecar")


_CLIENT: MossClient | None = None


def _client() -> MossClient:
    # One shared client for the process: load_index state lives on the client, so a new
    # client per request would query an unloaded runtime. Reuse a singleton.
    global _CLIENT
    if _CLIENT is None:
        pid, key = os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY")
        if not (pid and key):
            raise HTTPException(500, "MOSS_PROJECT_ID / MOSS_PROJECT_KEY not set in sidecar env")
        _CLIENT = MossClient(pid, key)
    return _CLIENT


class Doc(BaseModel):
    id: str
    text: str
    metadata: dict = Field(default_factory=dict)


class AddReq(BaseModel):
    docs: list[Doc]


class QueryReq(BaseModel):
    text: str
    top_k: int = 5
    alpha: float = 0.7


_loaded = False  # has the index been loaded into the runtime this process?


async def _index_exists(client) -> bool:
    indexes = await _retry(lambda: client.list_indexes())
    return INDEX in {ix.name for ix in indexes}


async def _ensure_loaded(client) -> bool:
    """Load the index into memory once; subsequent queries are sub-10ms."""
    global _loaded
    if _loaded:
        return True
    if not await _index_exists(client):
        return False
    await _retry(lambda: client.load_index(INDEX))
    _loaded = True
    return True


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "index": INDEX}


@app.get("/count")
async def count() -> dict:
    client = _client()
    try:
        ix = await _retry(lambda: client.get_index(INDEX))
        return {"count": int(getattr(ix, "doc_count", 0) or 0)}
    except Exception:
        return {"count": 0}


@app.post("/add")
async def add(req: AddReq) -> dict:
    global _loaded
    client = _client()
    docs = [DocumentInfo(id=d.id, text=d.text, metadata=d.metadata) for d in req.docs]
    if await _index_exists(client):
        await _retry(lambda: client.add_docs(INDEX, docs))
    else:
        await _retry(lambda: client.create_index(INDEX, docs, MODEL))
    _loaded = False  # force a reload so new docs are queryable
    return {"added": len(docs)}


@app.post("/clear")
async def clear() -> dict:
    global _loaded
    client = _client()
    if await _index_exists(client):
        await _retry(lambda: client.delete_index(INDEX))
    _loaded = False
    return {"cleared": True}


@app.post("/query")
async def query(req: QueryReq) -> dict:
    client = _client()
    if not await _ensure_loaded(client):
        return {"docs": []}
    res = await _retry(
        lambda: client.query(INDEX, req.text, QueryOptions(top_k=req.top_k, alpha=req.alpha))
    )
    return {
        "docs": [
            {"id": d.id, "text": d.text, "score": float(d.score), "metadata": getattr(d, "metadata", {}) or {}}
            for d in res.docs
        ]
    }
