"""WaterfallAgent — presents payment resolution options A through E
in strict order.

The LLM walks through each step; if declined, it moves to the next.
When the caller accepts any option, the agent calls accept_option
which stores the details and hands off to PaymentCaptureAgent.
"""

from __future__ import annotations

import logging
import math

from livekit.agents import RunContext, function_tool

from models import UserData
from agents.base import BaseAgent

logger = logging.getLogger("elite-agent.waterfall")


def _hardship_terms(balance: float) -> tuple[int, float]:
    """Return (max_months, min_monthly_payment) for hardship plan."""
    if balance < 750:
        return 12, 65.0
    if balance < 2000:
        return 18, 115.0
    if balance < 3500:
        return 24, 150.0
    if balance < 5000:
        return 27, 190.0
    # $5,000+
    raw = balance / 30
    minimum = max(200.0, math.ceil(raw / 10) * 10)
    return 30, minimum


def _build_waterfall_instructions(ud: UserData) -> str:
    a = ud.account
    balance = a.current_balance or "0"
    six_pmt = a.six_payment_amount or ""
    settle_open = a.settlement_open_amount or ""
    settle_floor = a.settlement_floor_amount or ""

    # Pre-compute hardship caps for the LLM prompt
    try:
        bal_f = float(balance.replace(",", "").replace("$", ""))
    except ValueError:
        bal_f = 0.0
    max_months, min_pmt = _hardship_terms(bal_f)

    # Pre-compute settlement ÷ 3
    try:
        settle_split = f"${round(float(settle_open.replace(',', '').replace('$', '')) / 3, 2)}"
    except (ValueError, ZeroDivisionError):
        settle_split = "the settlement amount divided by three"

    return f"""\
Present resolution options in this EXACT order. Do NOT skip ahead unless the current option is declined.
Do NOT number the options aloud. Do NOT say "option one" or "option two". Present each conversationally.

Step A — Full balance today: ${balance} in one payment.
Step B — Full balance in 6 monthly payments of ${six_pmt} each. State terms directly and ask if the first payment can be made today. Do NOT ask the caller how many payments they want.
Step C — Settlement in one payment of ${settle_open}. Emphasize the savings compared to the full balance of ${balance}.
Step D — Settlement in 3 monthly payments of {settle_split} each. State terms directly. Do NOT offer more than 3 settlement payments.
Step E — Hardship plan on the FULL balance with monthly payments only:
  Maximum {max_months} payments, minimum ${min_pmt}/month.

HARD RULES:
- Never go below the settlement floor of ${settle_floor}.
- Never exceed the payment caps above.
- Never calculate percentages aloud.
- For multi-payment options, always ask if the first payment can be made today.
- Stay in control. Do NOT let the caller design their own plan for Steps A through D.

When the caller accepts ANY option, call the accept_option tool with the details.
If the caller declines all options and wants to end the call, call the all_options_refused tool.

CRITICAL: If the caller disputes the debt — call handle_dispute immediately.
CRITICAL: If the caller requests cease and desist, says stop calling, or mentions an attorney — call the appropriate tool immediately.
"""


class WaterfallAgent(BaseAgent):
    def __init__(self):
        super().__init__(instructions="")  # set dynamically

    async def on_enter(self):
        ud = self.session.userdata
        phase = _build_waterfall_instructions(ud)
        self._instructions = self._build_instructions(phase)
        self.session.generate_reply()

    @property
    def instructions(self) -> str:
        return getattr(self, "_instructions", "")

    @instructions.setter
    def instructions(self, value: str):
        self._instructions = value

    @function_tool
    async def accept_option(
        self,
        context: RunContext[UserData],
        option: str,
        amount: float,
        is_multi_payment: bool = False,
        number_of_payments: int = 1,
        monthly_amount: float = 0.0,
    ):
        """Call this when the caller accepts a payment or arrangement option.

        Args:
            option: Which step was accepted — A, B, C, D, or E.
            amount: Total dollar amount for this resolution.
            is_multi_payment: True for Steps B, D, E (arrangements).
            number_of_payments: Total number of payments in the plan.
            monthly_amount: Per-payment amount for multi-payment plans.
        """
        ud = context.userdata
        ud.accepted_option = option.upper()
        ud.payment_amount = amount
        ud.is_multi_payment = is_multi_payment
        ud.plan_months = number_of_payments
        ud.monthly_amount = monthly_amount

        if option.upper() in ("A",):
            ud.payment_type = "full_balance"
        elif option.upper() in ("C",):
            ud.payment_type = "settlement"
        else:
            ud.payment_type = "arrangement"

        logger.info(
            "Option %s accepted  amount=%.2f multi=%s months=%d",
            ud.accepted_option, amount, is_multi_payment, number_of_payments,
        )
        from agents.payment import PaymentCaptureAgent
        return PaymentCaptureAgent()

    @function_tool
    async def all_options_refused(self, context: RunContext[UserData]):
        """Call this when the caller has declined all resolution options
        and wants to end the call."""
        from agents.closing import EndRefusedAgent
        return EndRefusedAgent()
