from eyebrain.embeddings import HashingEmbedder
from eyebrain.index import MomentIndex
from eyebrain.models import IndexedMoment, Moment


def test_search_retrieves_relevant_display_incident(tmp_path):
    index = MomentIndex(tmp_path, embedder=HashingEmbedder())
    index.add_moments(
        [
            Moment(
                camera_id="front",
                start_sec=10,
                end_sec=20,
                summary="The display gets knocked over by a backpack.",
                tags=["display", "knocked over"],
            ),
            Moment(
                camera_id="hallway",
                start_sec=30,
                end_sec=40,
                summary="The contractor leaves a toolbox beside the equipment rack.",
                tags=["contractor", "toolbox"],
            ),
        ]
    )

    results = index.search("When did the display get knocked over?", top_k=1)

    assert len(results) == 1
    assert results[0].moment.camera_id == "front"


def test_index_does_not_persist_raw_video_paths(tmp_path):
    index = MomentIndex(tmp_path, embedder=HashingEmbedder())
    index.add_moments(
        [
            Moment(
                camera_id="front",
                start_sec=1,
                end_sec=2,
                summary="A compact observation only.",
                source_ref="abc123",
            )
        ]
    )

    raw = (tmp_path / "moments.jsonl").read_text(encoding="utf-8")

    assert ".mp4" not in raw
    assert "/Users/" not in raw
    assert "abc123" in raw


def test_search_reembeds_when_stored_backend_does_not_match(tmp_path):
    index = MomentIndex(tmp_path, embedder=HashingEmbedder())
    stale = IndexedMoment(
        camera_id="hallway",
        start_sec=30,
        end_sec=40,
        summary="The contractor leaves a toolbox beside the equipment rack.",
        tags=["contractor", "toolbox"],
        embedding=[1.0],
        embedding_backend="fastembed",
    )
    index._write([stale])

    results = index.search("Where did the contractor leave the equipment?", top_k=1)

    assert len(results) == 1
    assert results[0].moment.camera_id == "hallway"


def test_search_filters_weak_matches_by_default(tmp_path):
    index = MomentIndex(tmp_path, embedder=HashingEmbedder())
    index.add_moments(
        [
            Moment(
                camera_id="front",
                start_sec=10,
                end_sec=20,
                summary="A person stands in front of an orange panel.",
                tags=["person", "orange panel"],
            )
        ]
    )

    assert index.search("Where did the contractor leave the equipment?") == []
