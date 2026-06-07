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
from ..embeddings import make_embedder
from ..index import MomentIndex
from ..rag.synthesize import synthesize_cited_answer

INSTRUCTIONS = (
    "You are eyebrain, a voice assistant for searching security-camera footage. "
    "For ANY question about what the cameras saw — people, objects, incidents, timing, "
    "or location — you MUST call the search_footage tool and then read its result back to "
    "the user almost verbatim, keeping the camera and timecode citation. Keep replies "
    "short and conversational. If search_footage says nothing was found, say so and invite "
    "a more specific question. Never invent events the tool did not return."
)

_index = MomentIndex(embedder=make_embedder(os.getenv("EYEBRAIN_EMBEDDER", "fastembed")))


def _build_tts():
    """Pick a TTS backend from env. MiniMax (sponsor) if configured, else Cartesia/Deepgram."""
    if os.getenv("MINIMAX_API_KEY"):
        # MiniMax exposes an OpenAI-compatible speech endpoint; route the OpenAI TTS plugin
        # at it so we don't depend on a dedicated plugin existing.
        from livekit.plugins import openai
        return openai.TTS(
            base_url=os.getenv("MINIMAX_TTS_BASE_URL", "https://api.minimax.io/v1"),
            api_key=os.environ["MINIMAX_API_KEY"],
            model=os.getenv("MINIMAX_TTS_MODEL", "speech-01"),
            voice=os.getenv("MINIMAX_TTS_VOICE", "female-qn-qingse"),
        )
    if os.getenv("CARTESIA_API_KEY"):
        from livekit.plugins import cartesia
        return cartesia.TTS()
    from livekit.plugins import deepgram
    return deepgram.TTS()


def build_entrypoint():
    """Imported lazily so the package imports fine without the voice extra installed."""
    from livekit import agents
    from livekit.agents import Agent, AgentSession, RunContext, function_tool
    from livekit.plugins import deepgram, openai, silero

    class EyebrainAgent(Agent):
        def __init__(self) -> None:
            super().__init__(instructions=INSTRUCTIONS)

        @function_tool
        async def search_footage(self, context: RunContext, question: str) -> str:
            """Search all security cameras for moments relevant to the question and return
            a cited answer. Use for any question about what the cameras observed."""
            results = _index.search(question, top_k=TOP_K)
            answer = synthesize_cited_answer(question, results)
            return answer.answer

    async def entrypoint(ctx: agents.JobContext) -> None:
        await ctx.connect()
        session = AgentSession(
            stt=deepgram.STT(model="nova-2"),
            # On-device LLM via Ollama's OpenAI-compatible API.
            llm=openai.LLM(
                model=LLM_MODEL,
                base_url=f"{OLLAMA_HOST}/v1",
                api_key="ollama",  # Ollama ignores the key
            ),
            tts=_build_tts(),
            vad=silero.VAD.load(),
        )
        await session.start(agent=EyebrainAgent(), room=ctx.room)
        await session.generate_reply(
            instructions="Greet the caller in one sentence and invite them to ask what the cameras saw."
        )

    return agents.WorkerOptions(entrypoint_fnc=entrypoint)


def main() -> None:
    from livekit import agents

    agents.cli.run_app(build_entrypoint())


if __name__ == "__main__":
    main()
