# eyebrain

On-device natural-language search for multi-camera security footage.

eyebrain turns camera-side observations into a compact searchable index. The central node stores summaries, tags, timestamps, camera IDs, and embeddings. It does not store raw video frames.

## Quick Start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

python scripts/seed_demo.py --reset
eyebrain ask "When did the display get knocked over?"
eyebrain ask "Where did the contractor leave the equipment?"
eyebrain ask "How long has table 12 been waiting on their order?"
```

## Commands

```bash
eyebrain ingest data/videos/front-door.mp4 --camera-id front-door
eyebrain ingest data/videos/front-door.mp4 --camera-id front-door --captions data/front-door.captions.jsonl
eyebrain ask "Where did the contractor leave the equipment?"
eyebrain list
```

Caption sidecars are useful during the hackathon because they let you connect any local vision model, manual labels, or Moss agent output without changing the retrieval layer. Each line is JSON:

```json
{"time_sec": 185, "summary": "Contractor leaves the yellow toolbox beside the north hallway equipment rack.", "tags": ["contractor", "equipment", "toolbox"]}
```

## Architecture

1. Camera node samples video locally.
2. A local vision summarizer emits compact observations.
3. The central node stores compact observations and local embeddings.
4. A question is embedded locally and matched against all cameras.
5. The answer cites the exact camera and time window.

The default embedder is deterministic and local so the demo runs without network access. Set `--embedder fastembed` after installing/caching FastEmbed models for stronger semantic retrieval.

For raw-video ingestion and local Ollama vision captions:

```bash
pip install -e ".[vision,semantic]"
ollama pull qwen2.5vl:3b
eyebrain ingest data/videos/front-door.mp4 --camera-id front-door --vision-model qwen2.5vl:3b
```

## Privacy Boundary

The index persists only:

- camera ID and optional camera name
- timestamp range
- summary and tags
- compact embedding vector
- non-sensitive source reference

Raw video paths, frames, and image bytes are not written to the central index.
