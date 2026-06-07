# 👁️ eyebrain

**Talk to your security cameras.** A local, on-device AI voice agent that lets businesses *ask* their cameras what happened — instead of scrubbing hours of footage across a dozen feeds.

Built at the **Conversational AI Hackathon @ Y Combinator** (#MossHack) — **Qwen · Moss · MiniMax · LiveKit**.

🌐 Runs fully local · 🎥 Demo: **[eyebrain — AI Voice Agent for Security Cameras | #MossHack @ YC](https://www.youtube.com/watch?v=yCXA9VVhuXQ)** · 💻 Repo: https://github.com/Evode-Manirahari/eyebrain

---

## 1. What is this?

Security cameras record everything, but nobody actually watches the footage — and when something goes wrong, finding the moment means scrubbing timelines and switching between feeds.

**eyebrain is the layer you talk to.** Point it at your cameras and just ask:

- *"What happened at the front desk?"*
- *"How long was the backpack on the floor?"*
- *"Is anyone working on laptops in the common area?"*

Under the hood it's a **distributed, multi-camera video-RAG system**:

- Each camera runs a **local vision model** that watches what it sees and turns it into compact text moments — **raw video never leaves the node.**
- Those moments (caption + camera + timecode) are embedded into a **central semantic index**.
- A natural-language question retrieves the most relevant moments **across every camera**, synthesizes a **cited** answer, **speaks it aloud**, and **jumps the video to the exact second**.

It's not a chatbot over a transcript. It's the real loop: on-device vision, multi-camera retrieval, three query modes (single-moment / duration / narrative), a confidence gate that refuses to make things up, and a resilient retriever that never breaks the demo.

> **Privacy is the architecture, not a feature.**

**Privacy boundary — the central index persists *only*:**
- camera ID + optional camera name
- timestamp range
- caption summary + tags
- the compact embedding vector
- a non-sensitive source reference (a hash, not a path)

**Never written to the index:** raw video, frames, image bytes, or file paths. The footage stays on the camera node; the only thing that travels is text. (Frames shown in the UI are pulled on demand from the *local* video — they're never centralized.)

---

## 2. Demo video (~60s)

**▶️ [Watch the demo](https://www.youtube.com/watch?v=yCXA9VVhuXQ)**

Run of show: all-cameras grid → drop a backpack on the Front Desk camera → ask by voice → spoken cited answer + the video jumps to the moment → switch cameras and ask again.

---

## 3. How we used Qwen, Moss, MiniMax & LiveKit

```
 Each camera (on-device)              Central node                  Answer + interface
┌───────────────────────┐      ┌────────────────────────┐      ┌─────────────────────────┐
│ frame ─▶ Qwen2.5-VL    │ only │  Moss                  │      │ Qwen2.5 (optional) /    │
│ captions what it sees  │─────▶│  hybrid semantic search│─────▶│ instant template answer │
│ (no video leaves node) │ text │  across all cameras    │ top  │  + cited camera/timecode│
└───────────────────────┘      └────────────────────────┘moments└──────────┬─────────────┘
        privacy line                  ~13ms warm                            │
                                                          MiniMax voice ◀────┘  + LiveKit agent
                                                          clip jumps to the second
```

### Qwen — the on-device eyes
**Qwen2.5-VL (3B)** runs **locally via Ollama** and captions every sampled frame (people, objects, actions, incidents) — this is the system's understanding of the world, and it never touches the cloud. We sample sparsely (1 frame / ~2s) so a one-minute clip indexes in ~1 minute. We also pulled **Qwen2.5 (3B)** for cited-answer *synthesis* (`EYEBRAIN_SYNTH=llm`), though we default to an instant template for latency (see §4). The vision is 100% Qwen.

### Moss — the central retrieval brain
**Moss** is the semantic-search runtime — eyebrain's "central server." Cameras send only compact text moments; Moss indexes them and serves **hybrid (semantic + keyword) retrieval across all cameras** in **~13ms warm**. Because the Moss native runtime has no macOS-x86_64 wheel (see §6), we run it in a **Linux container sidecar** and the app talks to it over loopback HTTP — the app never imports the native runtime. A `ResilientRetriever` falls back to a local on-device index if Moss is ever unavailable, so a hiccup never breaks the demo.

### MiniMax — the voice
**MiniMax** text-to-speech speaks every answer. We hit the intl `t2a_v2` endpoint (API-key auth, no Group ID needed), decode the hex-encoded MP3, and play it — ~2.2s, with browser speech as a zero-latency fallback. Voice: `English_Trustworth_Man`.

### LiveKit — the live voice agent
A **LiveKit Agents** worker (`livekit-agents` 1.5.x) registers with our LiveKit Cloud project and exposes a single `search_footage` tool that calls eyebrain's on-device retrieval. STT/TTS run on **LiveKit Inference** (billed to the `HACK-MOSS-YC` credits); the agent's reasoning LLM runs on-device via Ollama. You talk to it in the LiveKit Agents Playground.

---

## 4. Latency (measured, Intel i9 / CPU-only, no GPU)

The query path *is* the fast path — the only heavy step, vision captioning, is **offline ingestion** and never runs in the live loop.

| Live query stage | Latency |
|---|---|
| Cross-camera retrieval | **~8ms** local · **~13ms** Moss (warm) |
| **End-to-end `/api/ask`** → answer + citations | **~10ms** local · **~0.25s** Moss |
| Video clip seek (jumps to the exact second) | **~0.002s** |
| Spoken answer (MiniMax TTS) | ~2.2s, plays right after the text |

*Vision captioning (Qwen2.5-VL) is offline — ~1.9s/frame, run once at ingest — so it never touches the live query path.*

**Net feel:** ask → **answer + the video jumping to the moment in ~10ms** (local; ~0.25s via Moss), with the spoken reply a beat behind.

---

## 5. What we built during the hackathon

Everything in this repo was built during the event. Highlights:

- **On-device ingestion pipeline** — OpenCV frame sampling + Qwen2.5-VL captioning → compact `Moment` records (caption, camera, timecode, embedding).
- **Pluggable retrieval** — `Moss` (sidecar) or local `fastembed`, behind a `ResilientRetriever` (Moss-primary, local-fallback, never hard-fails).
- **Three query modes**, auto-routed by intent:
  - **single-moment** — "where was the bag left?"
  - **duration** — "how long was it there?" (measures the span)
  - **narrative** — "what happened / what did the person do?" (stitches the camera's timeline into a *first → then → finally* story, de-noising the verbose captions)
- **Confidence gate** — below a relevance floor, it honestly says *"I didn't see that"* instead of inventing a non-answer (so judge probes like "did you see a dog?" don't break it).
- **Multi-camera security console (web UI)** — tabs (All + per-camera), a camera grid you click to play, each camera's clean event "script," and a voice agent (mic) scoped to all cameras or one.
- **MiniMax TTS** spoken answers + **LiveKit** voice agent.
- **Moss Linux sidecar** (Docker) so the native runtime works on an Intel Mac.
- Tooling: ruff + mypy + GitHub Actions CI, 18 tests.

---

## 6. Honest feedback on the tools

**Qwen2.5-VL (Ollama)** — Strong on-device captioning for a 3B (read a name badge, a Coca-Cola can, a backpack). But it miscounts (3 people → "two"), mislabels fast motion (walking → "skateboarding"), and pads every caption with venue boilerplate. The 7B fixes accuracy but is unusably slow on CPU — this wants a GPU / Apple-Silicon edge.

**Moss** — ~13ms warm hybrid search; local-first model fits the privacy story perfectly. Friction: **no `macosx_x86_64` wheel** (`pip install moss` is unsatisfiable on Intel Mac → we ran it in a Linux sidecar; query needs the native runtime, no HTTP fallback); you **must reuse one `MossClient`** (a per-request client 500s after the first query); and the free **60-units/mo** quota burns fast (re-syncs → `429 USAGE_LIMIT_EXCEEDED`). A quota meter + per-op cost hint would help.

**MiniMax** — `t2a_v2` authenticates with **just an API key** (no Group ID) and the English voices sound great. One gotcha: audio comes back **hex-encoded inside JSON** — a line in the quickstart would save the discovery.

**LiveKit** — Clean Agents framework; the worker registered instantly and LiveKit Inference meant no extra STT/TTS keys. Two gotchas: the `entrypoint` **must be module-level** (dev mode forks + imports it by name), and an on-device CPU LLM is too slow for snappy turns — use a fast inference LLM, keep logic in tools.

**Environment (Intel i9 Mac)** — Most sharp edges were CPU-only / x86_64-macOS: no Moss wheel, slow Qwen, the broken Homebrew `ollama` (use the cask), OpenCV on AVFoundation (`avc1`, not `mp4v`). On Apple-Silicon / Linux+GPU, most of this vanishes.

---

## 7. Run it yourself

```bash
# one-time
make setup                      # installs deps (vision, semantic, web, moss client)
# start the official Ollama app, then pull the model:
ollama pull qwen2.5vl:3b

# bring up the demo (Moss-backed, on-device fallback)
make moss-up                    # Moss sidecar (Docker) — optional; falls back to local
make web                        # → http://127.0.0.1:8000

# add footage (each clip becomes a camera, captioned on-device)
python scripts/record_camera.py --camera-id front_desk --name "Front Desk" --seconds 15
#   ...or a folder of clips:  python scripts/ingest_folder.py ~/Desktop/clips --reset
make moss-sync                  # push moments into Moss (skip to stay local)

# live voice agent (LiveKit)
python -m eyebrain.voice.agent dev    # then talk to it in agents-playground.livekit.io
```

Pure on-device (no Moss dependency): `make web-local`. Demo script: [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md).

---

## License

MIT © 2026 Evode Manirahari.
