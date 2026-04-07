"""Elite Portfolio Management — Inbound Voice Agent (LiveKit).

Entry point.  Run with:
    python agent.py
or:
    livekit-agents start agent.py
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

from livekit.agents import AgentSession, JobContext, JobProcess, AgentServer
from livekit.plugins import openai, silero, telnyx
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

# Boosted keywords for STT accuracy on debt-collection terminology
BOOSTED_KEYWORDS = [
    "payment", "balance", "settlement", "arrangement", "account",
    "verification", "dispute", "attorney", "cease", "desist",
    "pago", "saldo", "deuda", "acuerdo",
]


@server.rtc_session(agent_name="epm-inbound")
async def entrypoint(ctx: JobContext):
    await ctx.connect()

    # Wait for the SIP caller to join the room
    participant = await ctx.wait_for_participant()

    # Extract caller phone from SIP participant attributes
    caller_phone = (
        participant.attributes.get("sip.phoneNumber")
        or participant.attributes.get("sip.calleeNumber")
        or ""
    )
    logger.info("Inbound call from %s (participant=%s)", caller_phone, participant.identity)

    # Shared state for the entire call
    userdata = UserData(
        room_name=ctx.room.name,
        participant_identity=participant.identity,
        caller_phone=caller_phone,
    )

    # ── Voice pipeline ──────────────────────────────────────────────
    #
    # STT & TTS routed through Telnyx (single-hop when SIP trunk is
    # also Telnyx).  LLM stays on OpenAI for tool-calling quality.
    #
    # To fall back to direct Deepgram/OpenAI TTS, set
    # USE_TELNYX_MEDIA=false in .env.

    use_telnyx = os.getenv("USE_TELNYX_MEDIA", "true").lower() == "true"

    if use_telnyx:
        stt = telnyx.STT(
            transcription_engine="deepgram",
            model="nova-3",
            language="en",
            smart_format=True,
            punctuate=True,
            interim_results=True,
            keyterm=BOOSTED_KEYWORDS,
            endpointing=300,
        )
        tts = telnyx.TTS(
            voice=os.getenv("TELNYX_TTS_VOICE", "Telnyx.NaturalHD.astra"),
        )
    else:
        from livekit.plugins import deepgram as dg_plugin
        stt = dg_plugin.STT(model="nova-3", language="en-US")
        tts = openai.TTS(model="tts-1", voice="onyx", speed=1.14)

    session = AgentSession[UserData](
        userdata=userdata,
        vad=ctx.proc.userdata["vad"],
        stt=stt,
        llm=openai.LLM(
            model="gpt-4.1",
            temperature=0,
        ),
        tts=tts,
        turn_detection=MultilingualModel(),
    )

    # Brief pause before speaking (Retell begin_message_delay_ms = 1200)
    await asyncio.sleep(BEGIN_MESSAGE_DELAY)

    # Start the conversation with the greeting agent
    await session.start(agent=GreetingAgent(), room=ctx.room)


# ── Main ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server.run()
