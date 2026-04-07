"""ManualLookupAgent — fallback when phone-based auto-lookup fails.

Asks the caller for their full name and date of birth, looks up
the account, verifies identity, delivers compliance, and hands off
to OpeningFrameAgent.
"""

from __future__ import annotations

import logging

from livekit.agents import RunContext, function_tool

import crm
from models import UserData
from agents.base import BaseAgent
from agents.greeting import _populate_account

logger = logging.getLogger("elite-agent.manual_lookup")

PHASE_INSTRUCTIONS = """\
The automatic phone lookup did not find an account.

Ask the caller for their full name and date of birth.
Once you have both, call the find_account tool.

CRITICAL: If the caller mentions an attorney or lawyer at any point, immediately call transfer_to_attorney.
CRITICAL: If the caller requests cease and desist or says stop calling, immediately call handle_cease_and_desist.

Do not guess or invent account details.
Do not discuss creditor, balance, or payment options before identity verification and compliance.
"""


class ManualLookupAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            instructions=self._build_instructions(PHASE_INSTRUCTIONS),
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def find_account(
        self,
        context: RunContext[UserData],
        full_name: str,
        date_of_birth: str,
    ):
        """Look up the account by the caller's name and date of birth.

        Args:
            full_name: The caller's full name as spoken.
            date_of_birth: The caller's date of birth (any reasonable format).
        """
        ud = context.userdata
        result = await crm.lookup_by_name(full_name, date_of_birth)
        _populate_account(ud, result)

        if not ud.account.found:
            logger.info("Manual lookup found no match")
            return "Account not found. Ask the caller to try again with a different name or date of birth. If this is the second failed attempt, call transfer_to_specialist."

        if ud.account.cease_desist or ud.account.has_active_dispute:
            logger.info("Account has restrictions — transferring")
            from agents.closing import TransferSpecialistAgent
            return TransferSpecialistAgent()

        # Account found — confirm identity inline
        return (
            f"Account found for {ud.account.full_name}. "
            f"Confirm: 'I have you as {ud.account.full_name} with a birth date of {ud.account.dob}. Is that correct?' "
            "Wait for confirmation, then call confirm_manual_identity."
        )

    @function_tool
    async def confirm_manual_identity(self, context: RunContext[UserData]):
        """Call this once the caller confirms their identity during
        manual lookup."""
        ud = context.userdata
        ud.identity_verified = True
        logger.info("Identity verified (manual) for account %s", ud.account.account_id)

        await crm.log_compliance(ud.account.account_id)
        ud.compliance_delivered = True

        from agents.opening import OpeningFrameAgent
        return (
            OpeningFrameAgent(),
            crm.MINI_MIRANDA,
        )
