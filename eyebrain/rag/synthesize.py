"""On-device cited-answer synthesis.

`rag.answer.build_cited_answer` (Codex) gives a fast, deterministic template answer and
is the always-available fallback. This module adds the headline capability: a local LLM
(Qwen via Ollama) reads ONLY the retrieved moments and writes a natural, grounded answer
that cites camera + timecode. Nothing leaves the node.

The contract is identical to `build_cited_answer` — it returns a `CitedAnswer` — so the
web and voice layers can swap synthesizers without caring which one ran."""

from __future__ import annotations

import os

from .. import config
from ..models import Citation, CitedAnswer, QueryResult
from .answer import build_cited_answer

SYSTEM_PROMPT = (
    "You are eyebrain, an assistant that answers questions about security-camera footage. "
    "You are given a list of observed MOMENTS, each with a camera, a timecode, and a "
    "description. Answer the user's question using ONLY these moments. Rules:\n"
    "- Be concise and direct (1-3 sentences) — your answer will be read aloud.\n"
    "- Always cite the camera and timecode you relied on, phrased naturally, e.g. 'on the "
    "Back Hallway camera at 00:47'. Never use bracket notation like '[cam2 @ 00:47]'.\n"
    "- If the moments do not contain the answer, say so plainly. Never invent events, "
    "people, times, or cameras that are not in the moments.\n"
    "- Lead with the answer (when/where/what), not with 'based on the footage'."
)


def fast_cited_answer(question: str, results: list[QueryResult]) -> CitedAnswer:
    """Instant (no-LLM) cited answer built from the top moment. The VLM summary already
    reads naturally, so we just frame it with the camera + timecode. ~0ms — the lowest-
    latency path, used by default for live demos."""
    if not results:
        return build_cited_answer(question, results)
    top = results[0].moment
    cam = top.camera_name or top.camera_id
    summary = top.summary.strip().rstrip(".")
    if summary:
        summary = summary[0].lower() + summary[1:]
    answer = f"On the {cam} camera at {top.time_range}, {summary}."
    return CitedAnswer(
        question=question,
        answer=answer,
        citations=[Citation.from_result(r) for r in results],
        metadata={"result_count": len(results), "synthesis": "fast"},
    )


def answer_for(question: str, results: list[QueryResult]) -> CitedAnswer:
    """Dispatch by EYEBRAIN_SYNTH: 'fast' (default, instant) or 'llm' (Qwen, ~7s on CPU)."""
    if os.getenv("EYEBRAIN_SYNTH", "fast").lower() == "llm":
        return synthesize_cited_answer(question, results)
    return fast_cited_answer(question, results)


def _format_moments(results: list[QueryResult]) -> str:
    # Natural phrasing (no [brackets]) so the LLM cites conversationally when read aloud.
    lines = []
    for i, r in enumerate(results, 1):
        m = r.moment
        cam = m.camera_name or m.camera_id
        lines.append(f"{i}. {cam} camera, at {m.time_range} (relevance {r.score:.2f}): {m.summary}")
    return "\n".join(lines)


def synthesize_cited_answer(
    question: str,
    results: list[QueryResult],
    *,
    model: str | None = None,
    host: str | None = None,
) -> CitedAnswer:
    """LLM-synthesized grounded answer. Falls back to the template answer if the local
    LLM is unavailable, so callers always get a usable `CitedAnswer`."""
    if not results:
        return build_cited_answer(question, results)

    try:
        import ollama

        client = ollama.Client(host=host or config.OLLAMA_HOST)
        resp = client.chat(
            model=model or config.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"MOMENTS:\n{_format_moments(results)}\n\nQUESTION: {question}",
                },
            ],
            options={"temperature": 0.2},
        )
        answer_text = (resp.get("message") or {}).get("content", "").strip()
        if not answer_text:
            raise ValueError("empty LLM response")
    except Exception as exc:  # pragma: no cover - falls back to deterministic template
        fallback = build_cited_answer(question, results)
        fallback.metadata["synthesis"] = f"fallback:{type(exc).__name__}"
        return fallback

    return CitedAnswer(
        question=question,
        answer=answer_text,
        citations=[Citation.from_result(r) for r in results],
        metadata={"result_count": len(results), "synthesis": "llm", "model": model or config.LLM_MODEL},
    )
