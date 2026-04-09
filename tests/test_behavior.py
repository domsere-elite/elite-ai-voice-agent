"""Behavioral tests for Elite Voice Agent using LiveKit's testing framework.

These tests exercise agent behavior end-to-end with an LLM, verifying
tool calls, handoffs, and response quality.  They require LiveKit Cloud
credentials (LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET).

Run with:
    pytest tests/test_behavior.py -v
"""

from __future__ import annotations

import os
import pytest

from livekit.agents import AgentSession, inference, mock_tools

from models import UserData
from agents.greeting import GreetingAgent
from agents.verify import VerifyIdentityAgent
from agents.manual_lookup import ManualLookupAgent
from agents.opening import OpeningFrameAgent
from agents.waterfall import WaterfallAgent

# Skip the entire module if LiveKit Cloud credentials are not set
pytestmark = pytest.mark.skipif(
    not os.getenv("LIVEKIT_API_KEY"),
    reason="LiveKit Cloud credentials required (set LIVEKIT_API_KEY)",
)

LLM_MODEL = "openai/gpt-4.1-mini"


# ── Helpers ────────────────────────────────────────────────────────────

def _make_userdata(**overrides) -> UserData:
    defaults = dict(
        room_name="test-room",
        participant_identity="test-caller",
        caller_phone="+15551234567",
    )
    defaults.update(overrides)
    return UserData(**defaults)


def _mock_lookup_found(phone: str = "") -> dict:
    return {
        "found": True,
        "account_id": "ACC-TEST-001",
        "elite_id": "ELT-TEST-001",
        "full_name": "Jane Smith",
        "first_name": "Jane",
        "last_name": "Smith",
        "dob": "03/15/1990",
        "current_balance": "2500.00",
        "original_creditor": "Test Bank",
        "bank_name": "Test National",
        "settlement_open_amount": "1500.00",
        "settlement_floor_amount": "1000.00",
        "six_payment_amount": "416.67",
        "cease_desist": False,
        "has_active_dispute": False,
    }


def _mock_lookup_not_found(phone: str = "") -> dict:
    return {"found": False}


# ── Greeting Agent Tests ──────────────────────────────────────────────

class TestGreetingBehavior:

    async def test_greeting_calls_lookup_on_response(self):
        """After caller responds, agent should call lookup_account."""
        async with (
            inference.LLM(model=LLM_MODEL) as llm,
            AgentSession(llm=llm, userdata=_make_userdata()) as session,
        ):
            await session.start(GreetingAgent())

            # First turn: agent delivers the greeting via on_enter
            await session.run(user_input="")

            # Second turn: caller responds, agent should call lookup
            with mock_tools(GreetingAgent, {
                "lookup_account": lambda ctx: _mock_lookup_found(),
            }):
                result = await session.run(
                    user_input="Hi, I'm calling about my account.",
                )

            result.expect.next_event().is_function_call(name="lookup_account")

    async def test_attorney_mention_triggers_transfer(self):
        """Mentioning an attorney should immediately trigger transfer."""
        async with (
            inference.LLM(model=LLM_MODEL) as llm,
            AgentSession(llm=llm, userdata=_make_userdata()) as session,
        ):
            await session.start(GreetingAgent())

            result = await session.run(
                user_input="I have an attorney handling this matter.",
            )

            result.expect.next_event().is_function_call(
                name="transfer_to_attorney",
            )


# ── Verify Identity Agent Tests ──────────────────────────────────────

class TestVerifyBehavior:

    async def test_identity_confirmed(self):
        """Caller confirming identity should trigger confirm_identity."""
        ud = _make_userdata()
        ud.account.found = True
        ud.account.full_name = "Jane Smith"
        ud.account.dob = "03/15/1990"
        ud.account.account_id = "ACC-TEST-001"

        async with (
            inference.LLM(model=LLM_MODEL) as llm,
            AgentSession(llm=llm, userdata=ud) as session,
        ):
            await session.start(VerifyIdentityAgent())

            with mock_tools(VerifyIdentityAgent, {
                "confirm_identity": lambda ctx: None,
            }):
                result = await session.run(
                    user_input="Yes, that's me.",
                )

            result.expect.next_event().is_function_call(name="confirm_identity")

    async def test_cease_desist_during_verify(self):
        """Cease-and-desist request during verify should trigger handler."""
        ud = _make_userdata()
        ud.account.found = True
        ud.account.full_name = "Jane Smith"
        ud.account.dob = "03/15/1990"

        async with (
            inference.LLM(model=LLM_MODEL) as llm,
            AgentSession(llm=llm, userdata=ud) as session,
        ):
            await session.start(VerifyIdentityAgent())

            result = await session.run(
                user_input="Stop calling me. I want you to cease and desist.",
            )

            result.expect.next_event().is_function_call(
                name="handle_cease_and_desist",
            )


# ── Waterfall Agent Tests ────────────────────────────────────────────

class TestWaterfallBehavior:

    async def test_presents_full_balance_first(self):
        """Agent should present full balance option first and not skip ahead."""
        ud = _make_userdata()
        ud.account.found = True
        ud.account.current_balance = "2500.00"
        ud.account.settlement_open_amount = "1500.00"
        ud.account.settlement_floor_amount = "1000.00"
        ud.account.six_payment_amount = "416.67"
        ud.identity_verified = True
        ud.compliance_delivered = True

        async with (
            inference.LLM(model=LLM_MODEL) as llm,
            AgentSession(llm=llm, userdata=ud) as session,
        ):
            await session.start(WaterfallAgent())

            # on_enter generates initial reply; caller says they're ready
            await session.run(user_input="")
            result = await session.run(
                user_input="Yes, I'd like to hear my options."
            )

            await result.expect.next_event().is_message(
                role="assistant",
            ).judge(
                llm,
                intent="Presents a payment option involving the full balance",
            )

    async def test_accept_option_called(self):
        """Caller accepting should trigger accept_option tool."""
        ud = _make_userdata()
        ud.account.found = True
        ud.account.current_balance = "2500.00"
        ud.account.settlement_open_amount = "1500.00"
        ud.account.settlement_floor_amount = "1000.00"
        ud.account.six_payment_amount = "416.67"
        ud.identity_verified = True
        ud.compliance_delivered = True

        async with (
            inference.LLM(model=LLM_MODEL) as llm,
            AgentSession(llm=llm, userdata=ud) as session,
        ):
            await session.start(WaterfallAgent())

            # on_enter greeting + caller prompts options
            await session.run(user_input="")
            await session.run(user_input="Yes, tell me my options.")

            with mock_tools(WaterfallAgent, {
                "accept_option": lambda ctx, **kw: None,
            }):
                # Caller accepts the full balance option
                result = await session.run(
                    user_input="Yes, I'll pay the full twenty five hundred today.",
                )

            result.expect.next_event().is_function_call(name="accept_option")

    async def test_dispute_during_waterfall(self):
        """Disputing the debt mid-waterfall should trigger handle_dispute."""
        ud = _make_userdata()
        ud.account.found = True
        ud.account.account_id = "ACC-TEST-001"
        ud.account.current_balance = "2500.00"
        ud.account.settlement_open_amount = "1500.00"
        ud.account.settlement_floor_amount = "1000.00"
        ud.account.six_payment_amount = "416.67"
        ud.identity_verified = True
        ud.compliance_delivered = True

        async with (
            inference.LLM(model=LLM_MODEL) as llm,
            AgentSession(llm=llm, userdata=ud) as session,
        ):
            await session.start(WaterfallAgent())

            result = await session.run(
                user_input="This debt is not mine. I dispute it.",
            )

            result.expect.next_event().is_function_call(name="handle_dispute")
