# Build coordination (Claude + Codex)

Two agents are building eyebrain in parallel. To avoid clobbering each other, we split
ownership. Trust the repo over any status doc; if you touch the other lane, leave a note.

## Converged decisions (verified working on this machine)
- **Hardware:** Intel i9 Mac, no CUDA / no Apple-Silicon accel. Ollama runs CPU-only.
- **Ollama:** the Homebrew *formula* is broken (missing `llama-server`). Use the **cask**
  (`/Applications/Ollama.app/.../ollama serve`). Models pulled: `qwen2.5vl:3b`, `qwen2.5:3b`.
- **VLM latency:** ~52s cold load, then **~1.9s/frame warm**. Captioning is an OFFLINE
  ingestion step — never run it in the live query path.
- **Embeddings:** run the demo with `--embedder fastembed`. The `hash` default is an
  offline safety net but it MISRANKS the key queries (semantic paraphrase fails).
- **Video I/O:** OpenCV here uses AVFoundation, not ffmpeg. `mp4v` fourcc fails to write;
  use **`avc1`** (H.264). Real H.264 mp4 footage reads fine.

## Lane ownership
- **Codex (core):** `models.py`, `embeddings.py`, `index.py`, `vision.py`,
  `ingest/video.py`, `rag/answer.py` (template fallback), `cli.py`. Owns the text-RAG spine.
- **Claude (additive layers):** `rag/synthesize.py` (LLM cited answers), `web/` (UI:
  retrieved frame thumbnails + seek-to-timestamp), `voice/` (LiveKit agent + MiniMax TTS),
  `scripts/` (demo footage + pre-index). Builds on the public API; does not edit core files.

## Public API the additive layers depend on (please keep stable)
- `eyebrain.index.MomentIndex(index_dir, embedder).search(question, top_k) -> list[QueryResult]`
- `eyebrain.models`: `Moment`, `QueryResult`, `Citation`, `CitedAnswer`
- `eyebrain.ingest.ingest_video(...)` and `load_caption_sidecar(...)`
- `eyebrain.embeddings.make_embedder(name)`
