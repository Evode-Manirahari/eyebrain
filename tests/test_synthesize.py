"""Synthesis tests that need no model server — they exercise the empty-result path and
the LLM-unavailable fallback (pointed at a dead host)."""

from eyebrain.models import Moment, QueryResult
from eyebrain.rag.synthesize import duration_answer, is_duration_query, synthesize_cited_answer


def _result() -> QueryResult:
    m = Moment(camera_id="cam2", camera_name="Back Hallway", start_sec=47, end_sec=49,
               summary="The contractor leaves a ladder and a drill by the rear exit.")
    return QueryResult(moment=m, score=0.9)


def test_empty_results_returns_no_match():
    ans = synthesize_cited_answer("anything?", [])
    assert ans.citations == []
    assert "could not find" in ans.answer.lower()


def test_duration_query_detection():
    assert is_duration_query("How long was the backpack there?")
    assert is_duration_query("for how long was the door open")
    assert not is_duration_query("Where was the backpack left?")


def test_duration_answer_measures_span():
    moments = [
        QueryResult(
            moment=Moment(camera_id="cam2", camera_name="Back Hallway", start_sec=s, end_sec=s + 2,
                          summary="a black backpack on the floor"),
            score=0.95,
        )
        for s in (0, 2, 4, 6, 8)
    ]
    ca, span = duration_answer("How long was the backpack there?", moments)
    assert ca.metadata["synthesis"] == "duration"
    assert ca.metadata["seconds"] >= 8
    assert "seconds" in ca.answer and "Back Hallway" in ca.answer
    assert len(span) == 5


def test_llm_unavailable_falls_back_to_template():
    # Unroutable host forces the ollama call to fail -> deterministic template fallback.
    ans = synthesize_cited_answer(
        "Where did the contractor leave the equipment?",
        [_result()],
        host="http://127.0.0.1:1",
    )
    assert ans.metadata.get("synthesis", "").startswith("fallback")
    assert len(ans.citations) == 1
    assert ans.citations[0].camera_id == "cam2"
    # The template answer still surfaces the cited moment.
    assert "Back Hallway" in ans.answer
