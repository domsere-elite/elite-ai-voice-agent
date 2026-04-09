"""Terminal agents — closing, refused-end, and SIP transfer agents."""

from __future__ import annotations

import logging
import os

from livekit import api
from livekit.agents import Agent, RunContext, function_tool

from models import UserData

logger = logging.getLogger("elite-agent.closing")

SPECIALIST_PHONE = os.getenv("SPECIALIST_PHONE", "+18333814416")


async def _sip_transfer(room_name: str, participant_identity: str, phone: str):
    """Execute a cold SIP transfer to *phone*."""
    try:
        async with api.LiveKitAPI() as lk:
            await lk.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=room_name,
                    participant_identity=participant_identity,
                    transfer_to=phone,
                )
            )
        logger.info("SIP transfer to %s succeeded", phone)
    except Exception:
        logger.exception("SIP transfer to %s failed", phone)


# ── Closing (payment successful) ────────────────────────────────────────

class ClosingAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "The payment was processed successfully. "
                "Say exactly: \"You're all set. I appreciate you taking the time today.\" "
                "Then end the conversation."
            ),
        )

    async def on_enter(self):
        self.session.generate_reply()


# ── End — all options refused ────────────────────────────────────────────

class EndRefusedAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "The caller has declined all payment options. "
                "Thank them for their time and let them know they can call back "
                "at any time if they change their mind. End the call politely."
            ),
        )

    async def on_enter(self):
        self.session.generate_reply()


# ── SIP transfer agents ─────────────────────────────────────────────────

class _TransferAgent(Agent):
    """Base for agents that say a message then transfer the call."""

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def execute_sip_transfer(self, context: RunContext[UserData]) -> str:
        """Transfers the SIP call to the specialist line."""
        ud = context.userdata
        await _sip_transfer(ud.room_name, ud.participant_identity, SPECIALIST_PHONE)
        return "Transfer initiated. Goodbye."


class TransferSpecialistAgent(_TransferAgent):
    def __init__(self):
        super().__init__(
            instructions=(
                "Say exactly: \"I need to connect you with a specialist who can "
                "assist further.\" Then call the execute_sip_transfer tool."
            ),
        )


class TransferAttorneyAgent(_TransferAgent):
    def __init__(self):
        super().__init__(
            instructions=(
                "Say exactly: \"I understand. Let me transfer you to a specialist "
                "who can help.\" Then call the execute_sip_transfer tool. "
                "Do NOT ask for any identity information or other details."
            ),
        )
