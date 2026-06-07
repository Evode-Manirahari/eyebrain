"""Push the local moment index into Moss (the sponsor retrieval runtime).

Flow: cameras are always ingested into the local index first (reliable, and the offline
fallback). This mirrors those compact moments — captions + camera/timecode metadata, never
video — into Moss so retrieval can run on Moss's sub-10ms hybrid search.

Usage:
  # after recording/ingesting cameras locally:
  MOSS_PROJECT_ID=... MOSS_PROJECT_KEY=... python scripts/sync_to_moss.py [--reset]
Then run the app with EYEBRAIN_RETRIEVER=moss.
"""

from __future__ import annotations

import argparse

from eyebrain.index import MomentIndex
from eyebrain.models import Moment
from eyebrain.rag.moss_index import MossIndex


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="Delete the Moss index before syncing")
    args = ap.parse_args()

    local = MomentIndex().load()
    if not local:
        print("Local index is empty. Ingest cameras first (make record-cam1 / record-cam2).")
        return

    # IndexedMoment -> plain Moment (drop embeddings; Moss embeds with moss-minilm).
    moments = [Moment.model_validate(m.model_dump(exclude={"embedding", "embedding_backend"})) for m in local]

    moss = MossIndex()
    if args.reset:
        moss.clear()
    n = moss.add_moments(moments)
    print(f"Synced {n} moments to Moss. Run the app with EYEBRAIN_RETRIEVER=moss.")


if __name__ == "__main__":
    main()
