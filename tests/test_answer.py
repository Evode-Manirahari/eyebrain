from eyebrain.models import Moment, QueryResult
from eyebrain.rag import build_cited_answer


def test_answer_contains_citation_window():
    moment = Moment(
        camera_id="north_hall",
        camera_name="North Hallway",
        start_sec=185,
        end_sec=205,
        summary="The contractor leaves equipment beside the north hallway rack.",
    )

    answer = build_cited_answer("Where did the contractor leave the equipment?", [QueryResult(moment=moment, score=0.8)])

    assert "North Hallway" in answer.answer
    assert answer.citations[0].time_range == "03:05-03:25"


def test_duration_answer_uses_cited_timestamps():
    seated = Moment(
        camera_id="dining_room",
        start_sec=900,
        end_sec=930,
        summary="Table 12 has been seated and menus are closed, but no food has arrived.",
        tags=["table 12", "waiting"],
    )
    waiting = Moment(
        camera_id="dining_room",
        start_sec=1140,
        end_sec=1170,
        summary="Table 12 is still waiting on their order after about four minutes with no plates on the table.",
        tags=["table 12", "waiting"],
    )
    delivered = Moment(
        camera_id="dining_room",
        start_sec=1320,
        end_sec=1350,
        summary="A server delivers food to table 12 after roughly seven minutes of waiting.",
        tags=["table 12", "food delivered"],
    )

    answer = build_cited_answer(
        "How long has table 12 been waiting on their order?",
        [
            QueryResult(moment=waiting, score=0.9),
            QueryResult(moment=seated, score=0.8),
            QueryResult(moment=delivered, score=0.7),
        ],
    )

    assert "Table 12 waited about 7 minutes" in answer.answer
    assert answer.metadata["answer_type"] == "duration"
