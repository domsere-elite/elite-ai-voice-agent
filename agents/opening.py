"""OpeningFrameAgent — discloses the account situation and transitions
to the payment waterfall.

This agent runs AFTER compliance (Mini-Miranda) has been delivered.
It tells the caller about the returned transaction / breach of contract,
asks "Would you care to explain what happened?", then discloses the
balance and offers to review resolution options.
"""

from __future__ import annotations

import logging

from livekit.agents import RunContext, function_tool

from models import UserData
from agents.base import BaseAgent

logger = logging.getLogger("elite-agent.opening")


def _build_opening_instructions(ud: UserData) -> str:
    a = ud.account

    creditor_line = ""
    if a.original_creditor:
        creditor_line = f" with {a.original_creditor}"

    bank_line = ""
    if a.bank_name:
        bank_line = f" from their bank ({a.bank_name})"

    chargeoff_line = ""
    if a.chargeoff_date:
        chargeoff_line = f" dating back to {a.chargeoff_date}"

    balance = a.current_balance or "the amount on file"

    return f"""\
Compliance has been delivered. The caller's identity is verified.

Disclose that your office has been retained to review a returned transaction{bank_line} which led to a breach of contract{creditor_line}{chargeoff_line}.
Do not fabricate missing fields. If a field is empty, skip it naturally.

Then ask exactly: "Would you care to explain what happened?"
Stop and wait for the caller to respond.

After they respond:
  1. Acknowledge briefly and empathetically.
  2. Disclose the current balance of ${balance}.
  3. Ask whether they would like to review options to resolve the account.
  4. Once they are ready, call the proceed_to_options tool.

CRITICAL: If the caller disputes the debt, says it is not theirs, or says they never took out this loan — immediately call handle_dispute.
CRITICAL: If the caller requests cease and desist, says stop calling, or demands no further contact — immediately call handle_cease_and_desist.
CRITICAL: If the caller mentions an attorney or lawyer — immediately call transfer_to_attorney.
"""


class OpeningFrameAgent(BaseAgent):
    def __init__(self):
        super().__init__(instructions="")  # set dynamically

    async def on_enter(self):
        ud = self.session.userdata
        phase = _build_opening_instructions(ud)
        self._instructions = self._build_instructions(phase)
        self.session.generate_reply()

    @property
    def instructions(self) -> str:
        return getattr(self, "_instructions", "")

    @instructions.setter
    def instructions(self, value: str):
        self._instructions = value

    @function_tool
    async def proceed_to_options(self, context: RunContext[UserData]):
        """Call this once the caller is ready to hear resolution options."""
        from agents.waterfall import WaterfallAgent
        return WaterfallAgent()
