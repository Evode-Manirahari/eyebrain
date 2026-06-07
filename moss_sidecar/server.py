"""Moss sidecar — a thin HTTP proxy around the Moss Python SDK.

The Moss native runtime ships no macOS x86_64 wheel, so on an Intel Mac we run this
inside a Linux x86_64 container (where the wheel exists) and let the main eyebrain app
(eyebrain.rag.moss_index.MossIndex) call it over loopback HTTP. The proxy is deliberately
dumb: it forwards {id, text, metadata} docs and {text, top_k, alpha} queries straight to
Moss. All Moment<->doc mapping stays on the app side.

Env: MOSS_PROJECT_ID, MOSS_PROJECT_KEY, MOSS_INDEX (default "eyebrain")."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from moss import DocumentInfo, MossClient, QueryOptions
from pydantic import BaseModel

INDEX = os.getenv("MOSS_INDEX", "eyebrain")
MODEL = os.getenv("MOSS_MODEL", "moss-minilm")

app = FastAPI(title="moss-sidecar")


def _client() -> MossClient:
    pid, key = os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY")
    if not (pid and key):
        raise HTTPException(500, "MOSS_PROJECT_ID / MOSS_PROJECT_KEY not set in sidecar env")
    return MossClient(pid, key)


class Doc(BaseModel):
    id: str
    text: str
    metadata: dict = {}


class AddReq(BaseModel):
    docs: list[Doc]


class QueryReq(BaseModel):
    text: str
    top_k: int = 5
    alpha: float = 0.7


async def _index_exists(client) -> bool:
    return INDEX in {ix.name for ix in await client.list_indexes()}


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "index": INDEX}


@app.get("/count")
async def count() -> dict:
    client = _client()
    try:
        ix = await client.get_index(INDEX)
        return {"count": int(getattr(ix, "document_count", 0) or 0)}
    except Exception:
        return {"count": 0}


@app.post("/add")
async def add(req: AddReq) -> dict:
    client = _client()
    docs = [DocumentInfo(id=d.id, text=d.text, metadata=d.metadata) for d in req.docs]
    if await _index_exists(client):
        await client.add_docs(INDEX, docs)
    else:
        await client.create_index(INDEX, docs, MODEL)
    return {"added": len(docs)}


@app.post("/clear")
async def clear() -> dict:
    client = _client()
    if await _index_exists(client):
        await client.delete_index(INDEX)
    return {"cleared": True}


@app.post("/query")
async def query(req: QueryReq) -> dict:
    client = _client()
    if not await _index_exists(client):
        return {"docs": []}
    await client.load_index(INDEX)
    res = await client.query(INDEX, req.text, QueryOptions(top_k=req.top_k, alpha=req.alpha))
    return {
        "docs": [
            {"id": d.id, "text": d.text, "score": float(d.score), "metadata": getattr(d, "metadata", {}) or {}}
            for d in res.docs
        ]
    }
