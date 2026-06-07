"""LiveKit voice agent for eyebrain — the sponsor (LiveKit) voice interface.

Pipeline: caller speaks in a LiveKit room -> STT -> a thin agent LLM that has ONE tool,
`search_footage` -> the tool runs eyebrain's fully on-device retrieval + cited synthesis
-> TTS reads the cited answer back. The agent LLM itself runs on-device too (Ollama's
OpenAI-compatible endpoint), so the only things that touch the cloud are speech-to-text,
text-to-speech, and the WebRTC transport. No video or footage index ever leaves the node.

STATUS: requires keys (LIVEKIT_URL/API_KEY/API_SECRET + an STT key, optional MiniMax TTS).
Not exercised in CI. When keys are available:  uv pip install -e '.[voice]'  then
  python -m eyebrain.voice.agent dev
and verify against the installed livekit-agents version (the API has moved across
releases; adjust plugin imports if needed).
"""

from __future__ import annotations

import os

from ..config import LLM_MODEL, OLLAMA_HOST, TOP_K
from ..rag.retriever import make_retriever
from ..rag.synthesize import synthesize_cited_answer

INSTRUCTIONS = (
    "You are eyebrain, a voice assistant for searching security-camera footage. "
    "For ANY question about what the cameras saw — people, objects, incidents, timing, "
    "or location — you MUST call the search_footage tool and then read its result back to "
    "the user almost verbatim, keeping the camera and timecode citation. Keep replies "
    "short and conversational. If search_footage says nothing was found, say so and invite "
    "a more specific question. Never invent events the tool did not return."
)

_retriever = make_retriever()


def _build_tts():
    """TTS for the live agent. Prefer an explicit Cartesia key; otherwise route through
    LiveKit Inference (billed to the HACK-MOSS-YC credits) so no extra provider key is
    needed. (MiniMax TTS is wired in the *web* demo via eyebrain.voice.minimax_tts; a
    native LiveKit MiniMax adapter is a future add.)"""
    if os.getenv("CARTESIA_API_KEY"):
        from livekit.plugins import cartesia
        return cartesia.TTS()
    return os.getenv("EYEBRAIN_LK_TTS", "cartesia/sonic-2")  # LiveKit Inference string


def _build_stt():
    """STT for the live agent. Explicit Deepgram key if present, else LiveKit Inference."""
    if os.getenv("DEEPGRAM_API_KEY"):
        from livekit.plugins import deepgram
        return deepgram.STT(model="nova-3")
    return os.getenv("EYEBRAIN_LK_STT", "deepgram/nova-3")  # LiveKit Inference string


# NOTE: `entrypoint` must be a MODULE-LEVEL function — LiveKit dev mode forks worker
# processes and imports it by qualified name, so a nested closure won't work. livekit
# imports stay inside the function body so `import eyebrain.voice.agent` is light.
async def entrypoint(ctx) -> None:
    from livekit.agents import Agent, AgentSession, RunContext, function_tool
    from livekit.plugins import openai, silero

    class EyebrainAgent(Agent):
        def __init__(self) -> None:
            super().__init__(instructions=INSTRUCTIONS)

        @function_tool
        async def search_footage(self, context: RunContext, question: str) -> str:
            """Search all security cameras for moments relevant to the question and return
            a cited answer. Use for any question about what the cameras observed."""
            results = _retriever.search(question, top_k=TOP_K)
            return synthesize_cited_answer(question, results).answer

    await ctx.connect()
    session = AgentSession(
        stt=_build_stt(),
        # On-device LLM via Ollama's OpenAI-compatible API (keeps reasoning on-device).
        llm=openai.LLM(model=LLM_MODEL, base_url=f"{OLLAMA_HOST}/v1", api_key="ollama"),
        tts=_build_tts(),
        vad=silero.VAD.load(),
    )
    await session.start(agent=EyebrainAgent(), room=ctx.room)
    await session.generate_reply(
        instructions="Greet the caller in one sentence and invite them to ask what the cameras saw."
    )


def main() -> None:
    from livekit import agents

    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
