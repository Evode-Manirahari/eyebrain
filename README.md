# 👁️ eyebrain

**Talk to your security cameras.** A local, on-device AI voice agent that lets businesses *ask* their cameras what happened — instead of scrubbing hours of footage across a dozen feeds.

Built at the **Conversational AI Hackathon @ Y Combinator** (#MossHack) — **Qwen · Moss · MiniMax · LiveKit**.

🌐 Runs fully local · 🎥 Demo: **[eyebrain — AI Voice Agent for Security Cameras | #MossHack @ YC](YOUR_YOUTUBE_LINK_HERE)** · 💻 Repo: https://github.com/Evode-Manirahari/eyebrain

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

> **Privacy is the architecture, not a feature.** The central index stores summaries, embeddings, camera IDs and timestamps — never raw frames.

---

## 2. Demo video (~60s)

**▶️ [Watch the demo](YOUR_YOUTUBE_LINK_HERE)**

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

The key architectural decision: **the slow part (vision) is offline; the live query path is fast.**

| Stage | Latency | Notes |
|---|---|---|
| Qwen2.5-VL captioning | ~52s cold load, then **~1.9s/frame** | **Offline ingestion** — never in the live path |
| Moss retrieval (warm) | **~13ms** | ~8s on the very first query (one-time index load) |
| Local fastembed retrieval | **~8ms** | the fallback path |
| Answer synthesis (template, default) | **~instant** | the VLM caption already reads well |
| Answer synthesis (Qwen LLM, optional) | ~7s | CPU-bound — why it's off by default |
| **End-to-end `/api/ask`** | **~0.25s** (Moss) / **~10ms** (local) | text answer + citations |
| MiniMax TTS | ~2.2s | spoken answer (plays after the text) |
| Video clip seek (cached transcode) | **~0.002s** | range-served mp4, jumps to the second |

**Net feel:** ask → **text answer + the video jumping to the moment in ~0.25s**, voice a moment later. Down from ~9s before we moved synthesis off the CPU LLM to the instant template.

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

### Qwen2.5-VL (via Ollama)
- **Did well:** genuinely good on-device captioning for a 3B model — it read a name badge, identified a Coca-Cola can, a backpack, and "head resting on the table." OpenAI-style image input via Ollama just worked.
- **Could be better:** (1) **Counting/state errors** — it called 3 people "two," and "head down asleep" read as "sitting." (2) **Hallucinates on fast motion** — labeled walking as "skateboarding" and a backpack as "a suitcase." (3) **Verbose, repetitive captions** — every frame trails into "…in an indoor setting with orange acoustic panels on the walls," which buries the actual action and makes naive de-dup collapse distinct events. (4) **7B is the obvious accuracy fix but unusable on a CPU** (~tens of seconds/frame on this Intel Mac) — the real lesson is this *wants* a GPU or Apple Silicon at the edge.

### Moss
- **Did well:** the local-first model is exactly right for this use case — **~13ms warm hybrid search**, and the privacy story ("only compact text leaves the camera") maps perfectly onto a "central server."
- **Bugs / friction we hit:**
  - **No `macosx_x86_64` wheel** for the native core (`inferedge-moss-core`) — `pip install moss` is *unsatisfiable* on an Intel Mac (arm64-mac, Linux-x86_64, and win wheels only). We had to run Moss in a **Linux container sidecar**. Query also requires the in-memory native runtime (no cloud query endpoint), so there's no pure-HTTP escape hatch.
  - **One shared client is mandatory.** Creating a `MossClient` per request 500s after the first query — `load_index` state lives on the client, so a fresh client queries an unloaded runtime. A note in the docs would save hours.
  - **Free-tier quota is easy to burn.** "60 monthly units" (oddly labeled "voice minutes") — our dev loop (`create_index`/`delete_index` on every re-sync, plus test queries) **exhausted it**, returning `429 USAGE_LIMIT_EXCEEDED`. A clearer quota meter + a "this op costs N units" hint would help a lot during iteration.
  - **Transient 503s** on the free tier — we added retry-with-backoff; the local fallback covers the rest.

### MiniMax
- **Did well:** the intl `t2a_v2` endpoint authenticates with **just an API key** (no Group ID), and the English voices sound great — drop-in for a polished spoken answer.
- **Could be better:** the response is **hex-encoded audio inside JSON** (not raw bytes or a URL), which is an unusual shape to discover; one line in the quickstart would help. Voice-id naming is also a bit opaque.

### LiveKit
- **Did well:** the Agents framework is clean; the worker registered with Cloud immediately, and routing STT/TTS through **LiveKit Inference** meant no extra provider keys.
- **Could be better:** (1) The agent `entrypoint` **must be a module-level function** — dev mode forks workers and imports it by qualified name, so a nested closure fails with `Can't get local object`. Easy to hit, not obvious. (2) Running the agent's reasoning LLM **on-device (CPU) is too slow** for snappy turn-taking — for a real-time voice loop you really want a fast (cloud-inference) LLM and keep the heavy lifting in tools.

### Environment (Intel i9 Mac — the through-line)
Almost every sharp edge traced back to **CPU-only, x86_64-macOS**: no Moss wheel, slow Qwen, the broken Homebrew `ollama` formula (missing `llama-server` → use the cask), and OpenCV using **AVFoundation not ffmpeg** (the `mp4v` fourcc fails to write — use `avc1`). On Apple Silicon or Linux+GPU, most of this evaporates. We leaned into it: the design assumes a modest edge device and keeps the live path off the slow model.

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
