"""Synthesis tests that need no model server — they exercise the empty-result path and
the LLM-unavailable fallback (pointed at a dead host)."""

from eyebrain.models import Moment, QueryResult
from eyebrain.rag.synthesize import synthesize_cited_answer


def _result() -> QueryResult:
    m = Moment(camera_id="cam2", camera_name="Back Hallway", start_sec=47, end_sec=49,
               summary="The contractor leaves a ladder and a drill by the rear exit.")
    return QueryResult(moment=m, score=0.9)


def test_empty_results_returns_no_match():
    ans = synthesize_cited_answer("anything?", [])
    assert ans.citations == []
    assert "could not find" in ans.answer.lower()


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
