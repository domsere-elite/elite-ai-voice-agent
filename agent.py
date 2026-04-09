"""Elite Portfolio Management — Inbound Voice Agent (LiveKit Cloud).

Entry point.  Run with:
    python agent.py
or:
    livekit-agents start agent.py

All AI models (LLM, STT, TTS) are served through LiveKit Inference —
no separate OpenAI / Deepgram / Telnyx API keys required.  Only your
LiveKit Cloud credentials (LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
are needed.
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

from livekit.agents import AgentSession, JobContext, JobProcess, AgentServer, inference
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from models import UserData
from agents.greeting import GreetingAgent

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("elite-agent")

server = AgentServer()

# ── Pre-warm heavy models once per worker process ───────────────────────

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model pre-warmed")

server.setup_fnc = prewarm

# ── Session entrypoint (one per inbound SIP call) ──────────────────────

BEGIN_MESSAGE_DELAY = 1.2  # seconds — matches Retell begin_message_delay_ms

# Model configuration (override via env vars)
STT_MODEL = os.getenv("STT_MODEL", "deepgram/nova-3")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4.1")
TTS_MODEL = os.getenv("TTS_MODEL", "deepgram/aura-2")
TTS_VOICE = os.getenv("TTS_VOICE", "apollo")


@server.rtc_session(agent_name="epm-inbound")
async def entrypoint(ctx: JobContext):
    await ctx.connect()

    participant = await ctx.wait_for_participant()

    caller_phone = (
        participant.attributes.get("sip.phoneNumber")
        or participant.attributes.get("sip.calleeNumber")
        or ""
    )
    logger.info("Inbound call from %s (participant=%s)", caller_phone, participant.identity)

    userdata = UserData(
        room_name=ctx.room.name,
        participant_identity=participant.identity,
        caller_phone=caller_phone,
    )

    session = AgentSession[UserData](
        userdata=userdata,
        vad=ctx.proc.userdata["vad"],
        stt=inference.STT(model=STT_MODEL, language="en"),
        llm=inference.LLM(model=LLM_MODEL, extra_kwargs={"temperature": 0}),
        tts=inference.TTS(model=TTS_MODEL, voice=TTS_VOICE),
        turn_detection=MultilingualModel(),
    )

    # Brief pause before speaking (Retell begin_message_delay_ms = 1200)
    await asyncio.sleep(BEGIN_MESSAGE_DELAY)

    # Start the conversation with the greeting agent
    await session.start(agent=GreetingAgent(), room=ctx.room)


# ── Main ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server.run()
