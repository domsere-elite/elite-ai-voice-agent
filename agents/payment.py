"""PaymentCaptureAgent — collects billing address + card via DTMF,
then processes the payment or sets up the arrangement.

ONE-TIME (Steps A / C): processLivePayment → ClosingAgent
MULTI-PAYMENT (Steps B / D / E): tokenizeCard → confirmArrangement → ClosingAgent

Card digits are collected through server-side DTMF capture and never
touch the LLM context (PCI-safe).
"""

from __future__ import annotations

import logging

from livekit.agents import RunContext, function_tool

import crm
from dtmf import DTMFCollector
from models import UserData
from agents.base import BaseAgent

logger = logging.getLogger("elite-agent.payment")


def _build_payment_instructions(ud: UserData) -> str:
    a = ud.account
    has_full_address = bool(a.billing_address_on_file and a.billing_address_on_file.strip())
    city_state_zip = f"{a.city}, {a.state} {a.zip}".strip(", ")

    if has_full_address:
        address_block = (
            f"A billing address is on file: {a.billing_address_on_file}. "
            "Read it back and ask the caller to confirm. "
            "If they confirm, call confirm_billing_address with confirmed=true. "
            "If they correct any part, use the corrected address and call confirm_billing_address with confirmed=false and the corrected fields."
        )
    elif city_state_zip and city_state_zip != ",":
        address_block = (
            f"Only city/state/zip are on file: {city_state_zip}. "
            f"Say: 'I only have {city_state_zip} on file. What is the street address for this card?' "
            "Wait for the street address, then confirm the full address and call confirm_billing_address."
        )
    else:
        address_block = (
            "No billing address is on file. "
            "Ask for the full billing address (street, city, state, zip) for the card. "
            "Then call confirm_billing_address."
        )

    return f"""\
The caller accepted a resolution option. Do NOT repeat the plan details or balance.
Move directly to collecting the billing address, then the card.

BILLING ADDRESS:
{address_block}

CARD CAPTURE (after billing address is confirmed):
- Tell the caller to enter card details by keypad ONLY. Never let them say card numbers aloud.
- Ask for ONE field at a time and wait silently after each instruction.
- Step 1: Say "Please enter your 16-digit card number on your keypad followed by the pound sign." Then call collect_card_number.
- Step 2: After card captured, say "Now enter the expiration date as six digits — two for the month and four for the year — followed by the pound sign. For example, April 2030 would be zero four two zero three zero." Then call collect_expiration.
- Step 3: After expiration captured, say "Finally, enter the three or four digit security code on the back of your card followed by the pound sign." Then call collect_cvv.
- After all three are captured, call process_payment_now.

If keypad capture fails twice for any field, call transfer_to_specialist.
"""


class PaymentCaptureAgent(BaseAgent):
    def __init__(self):
        super().__init__(instructions="")  # set dynamically

    async def on_enter(self):
        ud = self.session.userdata
        phase = _build_payment_instructions(ud)
        self._instructions = self._build_instructions(phase)
        # Store card details server-side only
        self._card_number = ""
        self._exp_month = ""
        self._exp_year = ""
        self._cvv = ""
        self.session.generate_reply()

    @property
    def instructions(self) -> str:
        return getattr(self, "_instructions", "")

    @instructions.setter
    def instructions(self, value: str):
        self._instructions = value

    # ── Billing address ─────────────────────────────────────────────────

    @function_tool
    async def confirm_billing_address(
        self,
        context: RunContext[UserData],
        street: str = "",
        city: str = "",
        state: str = "",
        zip_code: str = "",
        confirmed: bool = False,
    ):
        """Save the billing address. Call after the caller confirms or
        provides their billing address.

        Args:
            street: Street line of the billing address.
            city: City.
            state: Two-letter state code.
            zip_code: ZIP / postal code.
            confirmed: True ONLY if a full street address was already on
                       file and the caller confirmed it unchanged.
        """
        ud = context.userdata
        a = ud.account
        ud.billing_street = street or a.billing_address_on_file
        ud.billing_city = city or a.city
        ud.billing_state = state or a.state
        ud.billing_zip = zip_code or a.zip
        ud.address_confirmed = confirmed
        logger.info("Billing address set: %s, %s, %s %s (confirmed=%s)",
                     ud.billing_street, ud.billing_city, ud.billing_state,
                     ud.billing_zip, confirmed)
        return "Billing address saved. Now instruct the caller to enter their card number by keypad."

    # ── DTMF card capture (PCI-safe — digits never enter LLM) ──────────

    @function_tool
    async def collect_card_number(self, context: RunContext[UserData]) -> str:
        """Collect the 16-digit card number via DTMF keypad.
        Call this AFTER telling the caller to enter their card number."""
        room = context.session.room
        collector = DTMFCollector(room)
        result = await collector.collect(expected_digits=16, timeout_per_digit=10.0)
        if result.timed_out or len(result.digits) < 13:
            return "Card number capture timed out or was incomplete. Ask the caller to try again."
        self._card_number = result.digits
        last4 = result.digits[-4:]
        logger.info("Card captured ending in %s", last4)
        return f"Got it — card ending in {last4}. Now ask for the expiration date by keypad."

    @function_tool
    async def collect_expiration(self, context: RunContext[UserData]) -> str:
        """Collect the 6-digit expiration (MMYYYY) via DTMF keypad.
        Call this AFTER telling the caller to enter the expiration."""
        room = context.session.room
        collector = DTMFCollector(room)
        result = await collector.collect(expected_digits=6, timeout_per_digit=10.0)
        if result.timed_out or len(result.digits) < 6:
            return "Expiration capture failed. Ask the caller to try again."
        self._exp_month = result.digits[:2]
        self._exp_year = result.digits[2:]
        logger.info("Expiration captured: %s/%s", self._exp_month, self._exp_year)
        return "Thank you. Now ask for the security code by keypad."

    @function_tool
    async def collect_cvv(self, context: RunContext[UserData]) -> str:
        """Collect the 3- or 4-digit CVV via DTMF keypad.
        Call this AFTER telling the caller to enter the security code."""
        room = context.session.room
        collector = DTMFCollector(room)
        result = await collector.collect(expected_digits=4, timeout_per_digit=10.0)
        if result.timed_out or len(result.digits) < 3:
            return "Security code capture failed. Ask the caller to try again."
        self._cvv = result.digits[:4]
        logger.info("CVV captured (%d digits)", len(self._cvv))
        return "Got it. All card details captured. Now call process_payment_now to finalize."

    # ── Payment processing ──────────────────────────────────────────────

    @function_tool
    async def process_payment_now(self, context: RunContext[UserData]):
        """Process the payment using the captured card details.
        Call this after card number, expiration, and CVV are all captured."""
        ud = context.userdata
        a = ud.account

        billing_full = f"{ud.billing_street}, {ud.billing_city}, {ud.billing_state} {ud.billing_zip}"

        if not ud.is_multi_payment:
            # ── One-time payment (Step A or C) ──────────────────────
            result = await crm.process_payment(
                account_id=a.account_id,
                amount=ud.payment_amount,
                payment_type=ud.payment_type,
                card_number=self._card_number,
                exp_month=self._exp_month,
                exp_year=self._exp_year,
                cvv=self._cvv,
                cardholder_name=a.full_name,
                elite_id=a.elite_id,
                billing_address=billing_full,
                billing_street=ud.billing_street,
                billing_city=ud.billing_city,
                billing_state=ud.billing_state,
                billing_zip=ud.billing_zip,
                address_on_file_confirmed=ud.address_confirmed,
            )
            # Wipe card data from memory immediately
            self._card_number = ""
            self._cvv = ""

            if result.get("success"):
                logger.info("Payment succeeded: %s", result.get("transaction_id"))
                from agents.closing import ClosingAgent
                return ClosingAgent()
            else:
                decline = result.get("decline_reason", "unknown reason")
                logger.warning("Payment declined: %s", decline)
                return (
                    f"The payment was declined — {decline}. "
                    "Ask the caller if they would like to try a different card. "
                    "If yes, start card capture again (collect_card_number). "
                    "If no, call transfer_to_specialist."
                )
        else:
            # ── Multi-payment arrangement (Step B, D, E) ────────────
            # 1. Tokenize card
            tok_result = await crm.tokenize_card(
                a.account_id, billing_full,
            )
            token_id = tok_result.get("tokenized_card_id", "")
            if not token_id:
                self._card_number = ""
                self._cvv = ""
                logger.error("Card tokenization failed")
                return "Card tokenization failed. Ask if they want to try a different card or call transfer_to_specialist."

            # 2. Confirm arrangement
            arr_result = await crm.confirm_arrangement(
                account_id=a.account_id,
                tokenized_card_id=token_id,
                first_payment_date=ud.first_payment_date or "today",
                first_payment_amount=str(ud.monthly_amount),
                recurring_payment_amount=str(ud.monthly_amount) if ud.plan_months > 1 else "",
                recurring_day_of_month="",
            )
            # Wipe card data
            self._card_number = ""
            self._cvv = ""

            if arr_result.get("success", True):
                logger.info("Arrangement confirmed for account %s", a.account_id)
                from agents.closing import ClosingAgent
                return ClosingAgent()
            else:
                logger.warning("Arrangement confirmation failed")
                return "The arrangement could not be confirmed. Call transfer_to_specialist."
