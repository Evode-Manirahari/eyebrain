"""On-device cited-answer synthesis.

`rag.answer.build_cited_answer` (Codex) gives a fast, deterministic template answer and
is the always-available fallback. This module adds the headline capability: a local LLM
(Qwen via Ollama) reads ONLY the retrieved moments and writes a natural, grounded answer
that cites camera + timecode. Nothing leaves the node.

The contract is identical to `build_cited_answer` — it returns a `CitedAnswer` — so the
web and voice layers can swap synthesizers without caring which one ran."""

from __future__ import annotations

import os
import re

from .. import config
from ..models import Citation, CitedAnswer, QueryResult, format_seconds
from .answer import build_cited_answer

_DURATION_RE = re.compile(
    r"\b(how long|how much time|for how long|duration|how many (seconds|minutes))\b", re.I
)
_NARRATIVE_RE = re.compile(
    r"\b(what happened|what did|what'?s going on|what is happening|walk me through|"
    r"tell me what|describe what|step by step|sequence of events|what.* do(ing)?)\b",
    re.I,
)


def is_duration_query(question: str) -> bool:
    return bool(_DURATION_RE.search(question or ""))


def is_narrative_query(question: str) -> bool:
    return bool(_NARRATIVE_RE.search(question or ""))


# Venue/scene boilerplate the VLM repeats on every frame. We STRIP it (keeping the action,
# which often trails at the end like "…, working on a laptop") so distinct events read
# clearly and don't collapse into "a person sitting at a table" over and over.
_NOISE_RE = re.compile(
    r"(?:\bin (?:an?|the) (?:indoor|office|orange[- ]?walled|empty|dining)[\w\- ]*?"
    r"(?:setting|space|hallway|room|area|dining area)\b"
    r"|(?:with|featuring)[\w ]*?(?:acoustic|soundproofing)[\w ]*?panels[\w ]*?(?:on the walls)?"
    r"(?:\s+and\s+(?:white\s+)?ceiling[\w ]*)?"
    r"|(?:and\s+)?(?:white\s+)?ceiling (?:lights|tiles)[\w ]*"
    r"|with (?:orange\s+)?(?:white\s+)?tables and chairs[\w ]*"
    r"|in front of an orange wall[\w ]*"
    r"|on the walls(?:\s+and ceiling)?"
    r"|arranged (?:in rows|neatly|around[\w ]*))",
    re.I,
)


def _tidy(summary: str) -> str:
    """Strip repeated venue boilerplate, keep the action; return plain English."""
    s = _NOISE_RE.sub("", summary)
    s = re.sub(r"\s+lights\s+(?:above|hanging[\w ]*)", "", s, flags=re.I)  # dangling "lights above"
    s = re.sub(r"\s*,\s*,", ",", s)            # ", ,"
    s = re.sub(r"\s{2,}", " ", s)              # double spaces
    s = re.sub(r"\s+([,.])", r"\1", s)         # space before punct
    s = s.strip().strip(",").strip().rstrip(".")
    return s


def _similar(a: str, b: str) -> bool:
    """True if two captions are near-duplicates (so we collapse repeated frames)."""
    aw, bw = set(a.lower().split()), set(b.lower().split())
    if not aw or not bw:
        return False
    return len(aw & bw) / len(aw | bw) > 0.6


def _dedupe_sequence(moments: list[QueryResult], cap: int = 6) -> list[QueryResult]:
    """Collapse consecutive near-identical captions so a narrative reads as distinct
    events, not the same frame repeated. Always keeps the last (the outcome)."""
    kept: list[QueryResult] = []
    for r in moments:
        if kept and _similar(_tidy(kept[-1].moment.summary), _tidy(r.moment.summary)):
            continue
        kept.append(r)
    if moments and (not kept or kept[-1] is not moments[-1]) and not (
        kept and _similar(kept[-1].moment.summary, moments[-1].moment.summary)
    ):
        kept.append(moments[-1])
    if len(kept) > cap:  # keep first, last, and evenly-spaced middles
        idxs = sorted({0, len(kept) - 1, *(round(i * (len(kept) - 1) / (cap - 1)) for i in range(cap))})
        kept = [kept[i] for i in idxs]
    return kept


def _span(results: list[QueryResult], cutoff_ratio: float = 0.65):
    """Pick the top camera and the run of relevant moments on it, and return the time span
    they cover. `cutoff_ratio` gates relevance relative to the top hit — duration uses a
    tight gate (the exact subject), narrative a looser one (the surrounding sequence)."""
    top = results[0]
    cam_id = top.moment.camera_id
    cutoff = max(0.0, top.score * cutoff_ratio)
    span = [r for r in results if r.moment.camera_id == cam_id and r.score >= cutoff]
    if not span:
        span = [top]
    span.sort(key=lambda r: r.moment.start_sec)
    start = min(r.moment.start_sec for r in span)
    end = max(r.moment.end_sec for r in span)
    return cam_id, start, end, span


def _fmt_duration(seconds: float) -> str:
    s = max(0, round(seconds))
    if s < 60:
        return f"{s} seconds"
    m, s = divmod(s, 60)
    return f"{m} min {s} sec" if s else f"{m} min"


def duration_answer(question: str, results: list[QueryResult]) -> tuple[CitedAnswer, list[QueryResult]]:
    """Answer a 'how long' question by measuring the span the subject is present."""
    if not results:
        return build_cited_answer(question, results), results
    cam_id, start, end, span = _span(results)
    cam = span[0].moment.camera_name or cam_id
    answer = (
        f"On the {cam} camera, it was there for about {_fmt_duration(end - start)}, "
        f"from {format_seconds(start)} to {format_seconds(end)}."
    )
    ca = CitedAnswer(
        question=question,
        answer=answer,
        citations=[Citation.from_result(r) for r in span],
        metadata={"synthesis": "duration", "result_count": len(span), "seconds": round(end - start)},
    )
    return ca, span


def narrative_answer(question: str, results: list[QueryResult]) -> tuple[CitedAnswer, list[QueryResult]]:
    """Answer 'what happened? / what did he do?' by stitching the relevant moments into a
    chronological story (first -> then -> finally), collapsing repeated frames."""
    if not results:
        return build_cited_answer(question, results), results
    # Narrate the top camera's FULL timeline (cutoff 0) so the whole arc shows — not just
    # the frames most relevant to the query (which would clip the ending).
    cam_id, _, _, span = _span(results, cutoff_ratio=0.0)
    seq = _dedupe_sequence(sorted(span, key=lambda r: r.moment.start_sec))
    cam = seq[0].moment.camera_name or cam_id

    def phrase(r: QueryResult) -> str:
        s = _tidy(r.moment.summary)
        return (s[0].lower() + s[1:]) if s else s

    n = len(seq)
    if n == 1:
        body = f"{phrase(seq[0])} (at {format_seconds(seq[0].moment.start_sec)})"
    else:
        parts = []
        for i, r in enumerate(seq):
            lead = "first, " if i == 0 else ("and finally, " if i == n - 1 else "then ")
            parts.append(f"{lead}{phrase(r)} ({format_seconds(r.moment.start_sec)})")
        body = "; ".join(parts)
    answer = f"On the {cam} camera, here's what happened — {body}."
    ca = CitedAnswer(
        question=question,
        answer=answer,
        citations=[Citation.from_result(r) for r in seq],
        metadata={"synthesis": "narrative", "result_count": len(seq)},
    )
    return ca, seq


def _not_found(question: str) -> CitedAnswer:
    return CitedAnswer(
        question=question,
        answer="I didn't see anything matching that across the cameras. Try asking about a "
        "person, an object, or something that happened.",
        citations=[],
        metadata={"synthesis": "not_found", "result_count": 0},
    )


def answer_query(retriever, question: str, top_k: int = 5) -> tuple[CitedAnswer, list[QueryResult]]:
    """Top-level entry for web/voice. Routes by intent:
    - 'how long' -> duration span; 'what happened / what did X do' -> chronological
    narrative; otherwise the instant single-moment cited answer. Returns (answer, results)
    so the caller renders citations from the same moments the answer used.

    First a confidence gate: if even the best match is weak, say 'I didn't see that' rather
    than return an irrelevant moment — so out-of-scope probes don't produce non-answers."""
    floor = float(os.getenv("EYEBRAIN_ANSWER_FLOOR", "0.55"))
    probe = retriever.search(question, top_k=1, min_score=0.0)
    if not probe or probe[0].score < floor:
        return _not_found(question), []

    if is_duration_query(question):
        return duration_answer(question, retriever.search(question, top_k=50))
    if is_narrative_query(question):
        # min_score=0 so the FULL camera timeline is available (weak-but-temporal frames
        # like 'using laptop' aren't filtered out of the story).
        return narrative_answer(question, retriever.search(question, top_k=80, min_score=0.0))
    results = retriever.search(question, top_k=top_k)
    return answer_for(question, results), results

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
