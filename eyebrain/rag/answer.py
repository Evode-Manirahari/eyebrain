from __future__ import annotations

import re

from eyebrain.models import CitedAnswer, Citation, QueryResult


def build_cited_answer(question: str, results: list[QueryResult]) -> CitedAnswer:
    if not results:
        return CitedAnswer(
            question=question,
            answer=(
                "I could not find a matching moment in the compact camera index. "
                "Try a more specific object, location, or action."
            ),
            citations=[],
            metadata={"result_count": 0},
        )

    citations = [Citation.from_result(result) for result in results]
    duration_answer = _build_duration_answer(question, results)
    if duration_answer is not None:
        return CitedAnswer(
            question=question,
            answer=duration_answer,
            citations=citations,
            metadata={"result_count": len(results), "answer_type": "duration"},
        )

    top = results[0].moment
    answer_parts = [
        f"The best match is on {top.display_camera} at {top.time_range}: {top.summary}",
    ]
    if len(results) > 1:
        answer_parts.append(f"I found {len(results)} cited moments across the local index.")
    answer_parts.append("Use the citations to inspect only the relevant raw footage window on the camera node.")
    return CitedAnswer(
        question=question,
        answer=" ".join(answer_parts),
        citations=citations,
        metadata={"result_count": len(results)},
    )


def _build_duration_answer(question: str, results: list[QueryResult]) -> str | None:
    if "how long" not in question.lower():
        return None

    moments = [result.moment for result in results]
    start_candidates = [
        moment
        for moment in moments
        if _contains_any(moment.summary, ("seated", "waiting", "no food", "no plates", "order"))
    ]
    delivery_candidates = [
        moment
        for moment in moments
        if _contains_any(moment.summary, ("deliver", "delivers", "delivered", "food arrived"))
        or any("delivered" in tag.lower() for tag in moment.tags)
    ]
    if not start_candidates:
        return None

    start = min(start_candidates, key=lambda moment: moment.start_sec)
    delivery_after_start = [moment for moment in delivery_candidates if moment.start_sec >= start.start_sec]
    if not delivery_after_start:
        return None

    end = min(delivery_after_start, key=lambda moment: moment.start_sec)
    duration_seconds = max(0, end.start_sec - start.start_sec)
    if duration_seconds == 0:
        return None

    label = _subject_label(question, start.summary)
    minutes = duration_seconds / 60
    if minutes >= 1:
        duration = f"about {round(minutes):g} minute{'s' if round(minutes) != 1 else ''}"
    else:
        duration = f"about {round(duration_seconds):g} seconds"
    return (
        f"{label} waited {duration}, from {start.time_range} until delivery at {end.time_range}. "
        f"The clearest waiting checkpoint is {results[0].moment.time_range}: {results[0].moment.summary}"
    )


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    haystack = text.lower()
    return any(needle in haystack for needle in needles)


def _subject_label(question: str, fallback: str) -> str:
    match = re.search(r"\btable\s+\d+\b", question.lower()) or re.search(r"\btable\s+\d+\b", fallback.lower())
    if match:
        return match.group(0).title()
    return "The subject"
