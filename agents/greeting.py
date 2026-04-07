"""GreetingAgent — first agent in the flow.

Greets the caller, auto-looks-up their account by phone, and routes:
  • account found → VerifyIdentityAgent
  • account not found → ManualLookupAgent
  • cease_desist / active_dispute → TransferSpecialistAgent
"""

from __future__ import annotations

import logging

from livekit.agents import RunContext, function_tool

import crm
from models import UserData, AccountData
from agents.base import BaseAgent

logger = logging.getLogger("elite-agent.greeting")

PHASE_INSTRUCTIONS = """\
You are beginning an inbound call.

Say exactly: "Thank you for calling Elite Portfolio Management, my name is Erik — how can I help you today?"

Wait for the caller to respond. Listen carefully to their first response.

CRITICAL: If the caller mentions an attorney, lawyer, or legal representation, immediately call transfer_to_attorney.
CRITICAL: If the caller requests cease and desist, says stop calling, or demands no further contact, immediately call handle_cease_and_desist.

If the caller does NOT mention an attorney or request cease and desist, call the lookup_account tool to look up their account.
"""


class GreetingAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            instructions=self._build_instructions(PHASE_INSTRUCTIONS),
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def lookup_account(self, context: RunContext[UserData]):
        """Look up the caller's account by their phone number. Call this
        after the caller responds to the greeting (unless they mention
        an attorney or request cease/desist)."""
        ud = context.userdata
        phone = ud.caller_phone

        if not phone:
            logger.warning("No caller phone available — skipping to manual lookup")
            from agents.manual_lookup import ManualLookupAgent
            return ManualLookupAgent()

        result = await crm.lookup_by_phone(phone)
        _populate_account(ud, result)

        if ud.account.cease_desist:
            logger.info("Account has cease-desist flag — transferring")
            from agents.closing import TransferSpecialistAgent
            return TransferSpecialistAgent()

        if ud.account.has_active_dispute:
            logger.info("Account has active dispute — transferring")
            from agents.closing import TransferSpecialistAgent
            return TransferSpecialistAgent()

        if not ud.account.found:
            logger.info("Phone lookup returned no match — manual lookup")
            from agents.manual_lookup import ManualLookupAgent
            return ManualLookupAgent()

        logger.info("Account found: %s — proceeding to identity verification", ud.account.account_id)
        from agents.verify import VerifyIdentityAgent
        return VerifyIdentityAgent()


def _populate_account(ud: UserData, data: dict):
    """Map CRM response fields into the shared AccountData."""
    a = ud.account
    a.found = bool(data.get("found", False))
    a.account_id = str(data.get("account_id", ""))
    a.elite_id = str(data.get("elite_id", ""))
    a.full_name = str(data.get("full_name", ""))
    a.first_name = str(data.get("first_name", ""))
    a.last_name = str(data.get("last_name", ""))
    a.dob = str(data.get("dob", ""))
    a.phone = str(data.get("phone", ""))
    a.email = str(data.get("email", ""))
    a.current_balance = str(data.get("current_balance", ""))
    a.original_creditor = str(data.get("original_creditor", ""))
    a.bank_name = str(data.get("bank_name", ""))
    a.chargeoff_date = str(data.get("chargeoff_date", ""))
    a.portfolio_id = str(data.get("portfolio_id", ""))
    a.settlement_open_amount = str(data.get("settlement_open_amount", ""))
    a.settlement_floor_amount = str(data.get("settlement_floor_amount", ""))
    a.six_payment_amount = str(data.get("six_payment_amount", ""))
    a.billing_address_on_file = str(data.get("billing_address_on_file", ""))
    a.city = str(data.get("city", ""))
    a.state = str(data.get("state", ""))
    a.zip = str(data.get("zip", ""))
    a.status = str(data.get("status", ""))
    a.original_account_number = str(data.get("original_account_number", ""))
    a.cease_desist = bool(data.get("cease_desist", False))
    a.has_active_dispute = bool(data.get("has_active_dispute", False))
