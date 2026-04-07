"""VerifyIdentityAgent — confirms the caller is the account holder.

Uses the name and DOB from the auto-lookup.  On success, delivers
Mini-Miranda compliance and hands off to OpeningFrameAgent.
"""

from __future__ import annotations

import logging

from livekit.agents import RunContext, function_tool

import crm
from models import UserData
from agents.base import BaseAgent

logger = logging.getLogger("elite-agent.verify")

PHASE_INSTRUCTIONS = """\
You need to verify the caller's identity before discussing any account details.

Say: "I can go into more detail for you, I just have to confirm I am speaking to {name} with a birth date of {dob}. Is that correct?"

Use the ACTUAL name and date of birth — do not say placeholders.
Wait for a clear yes or correct.
If the response is vague, ask again.
If they say a different name, say: "My apologies, this number was given to me for the account holder on file. May I ask who I have reached?"
If verification fails twice, call transfer_to_specialist.

CRITICAL: If the caller mentions an attorney or lawyer at any point, immediately call transfer_to_attorney.
CRITICAL: If the caller requests cease and desist or says stop calling, immediately call handle_cease_and_desist.

When the caller confirms their identity, call the confirm_identity tool.
"""


class VerifyIdentityAgent(BaseAgent):
    def __init__(self):
        super().__init__(instructions="")  # set dynamically in on_enter

    async def on_enter(self):
        ud = self.session.userdata
        a = ud.account
        instructions = PHASE_INSTRUCTIONS.format(
            name=a.full_name or "the account holder",
            dob=a.dob or "the date of birth on file",
        )
        self._instructions = self._build_instructions(instructions)
        self.session.generate_reply()

    @property
    def instructions(self) -> str:
        return getattr(self, "_instructions", "")

    @instructions.setter
    def instructions(self, value: str):
        self._instructions = value

    @function_tool
    async def confirm_identity(self, context: RunContext[UserData]):
        """Call this once the caller has confirmed they are the account
        holder (said yes, correct, or otherwise affirmed)."""
        ud = context.userdata
        ud.identity_verified = True
        logger.info("Identity verified for account %s", ud.account.account_id)

        # Deliver Mini-Miranda compliance
        await crm.log_compliance(ud.account.account_id)
        ud.compliance_delivered = True

        from agents.opening import OpeningFrameAgent
        return (
            OpeningFrameAgent(),
            crm.MINI_MIRANDA,
        )

    @function_tool
    async def identity_failed(self, context: RunContext[UserData]):
        """Call this when identity verification has failed after two
        attempts — the caller denied being the account holder or gave
        a different name twice."""
        from agents.manual_lookup import ManualLookupAgent
        return ManualLookupAgent()
