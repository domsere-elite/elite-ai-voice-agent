"""BaseAgent — carries the global prompt and common interrupt tools.

Every conversation-phase agent inherits from this so attorney-mention,
cease-and-desist, and dispute handling are always available without
duplicating tool definitions.
"""

from __future__ import annotations

import logging

from livekit.agents import Agent, RunContext, function_tool

import crm
from models import UserData

logger = logging.getLogger("elite-agent")

# ── Global system prompt (prepended to every agent's instructions) ──────

GLOBAL_PROMPT = """\
Your name is Erik. You are an inbound customer service agent for Elite Portfolio Management.
Be professional, empathetic, concise, calm, and conversational.

IDENTITY AND PRIVACY RULES
- Never reveal account details, balance, creditor name, or payment options before identity is verified and compliance has played.
- Name and date of birth may be spoken for identity verification only.
- Never read SSN digits aloud.
- Never read back or confirm SSN, last 4 of SSN, email address, or full phone number.
- Do not discuss the debt with anyone other than the verified account holder.

COMPLIANCE RULES
- CRITICAL ATTORNEY OVERRIDE: If the caller mentions an attorney, lawyer, or legal representation at ANY point — even before identity is verified — immediately call the transfer_to_attorney tool. Do NOT ask for identity information after this point.
- If the caller says stop calling, do not call, cease and desist, or similar — immediately call the handle_cease_and_desist tool.
- If the caller disputes the debt or says it is not theirs — immediately call the handle_dispute tool.
- Never threaten, harass, or use abusive language.
- Never say garnish wages, sue you, legal action, report to credit bureau, arrest, jail, or seize property.

TRANSFER RULES
- If the caller asks for a human, first say: "I am fully equipped to help you with your file. Could you let me know what you would like to discuss? If I cannot help you I will transfer you right away."
- If they insist, call transfer_to_specialist.

INFORMATION BOUNDARY
- If the caller asks about office hours, location, number of employees, company history, website, or any company detail NOT in this prompt — say: "That's not something I have in front of me, but I can transfer you to someone who can help with that."
- Never fabricate account data. If data is missing, say: "That's not in the file I have."

SPEECH RULES
- Always speak dollar amounts naturally without saying "dot" or reading decimals for whole numbers.
- Say dates as spoken words. Do not read punctuation marks aloud.
- Never calculate percentages aloud.
"""


class BaseAgent(Agent):
    """Provides the global prompt prefix and universal interrupt tools."""

    def _build_instructions(self, phase_instructions: str) -> str:
        return GLOBAL_PROMPT + "\n\n" + phase_instructions

    # ── Attorney override (highest priority) ────────────────────────────

    @function_tool
    async def transfer_to_attorney(self, context: RunContext[UserData]):
        """Call this IMMEDIATELY if the caller mentions an attorney, lawyer,
        or legal representation at any point during the conversation."""
        from agents.closing import TransferAttorneyAgent
        return TransferAttorneyAgent()

    # ── Cease and desist ────────────────────────────────────────────────

    @function_tool
    async def handle_cease_and_desist(
        self, context: RunContext[UserData], note: str = ""
    ):
        """Call this if the caller requests cease and desist, says stop
        calling, or demands no further contact."""
        ud = context.userdata
        if ud.account.account_id:
            await crm.log_cease_and_desist(ud.account.account_id, note)
        from agents.closing import TransferAttorneyAgent
        return TransferAttorneyAgent()

    # ── Dispute ─────────────────────────────────────────────────────────

    @function_tool
    async def handle_dispute(
        self, context: RunContext[UserData], reason: str = ""
    ):
        """Call this if the caller disputes the debt or says it is not
        theirs."""
        ud = context.userdata
        if ud.account.account_id:
            await crm.log_dispute(ud.account.account_id, reason)
        from agents.closing import TransferSpecialistAgent
        return TransferSpecialistAgent()

    # ── Generic specialist transfer ─────────────────────────────────────

    @function_tool
    async def transfer_to_specialist(self, context: RunContext[UserData]):
        """Transfer the caller to a live specialist."""
        from agents.closing import TransferSpecialistAgent
        return TransferSpecialistAgent()
