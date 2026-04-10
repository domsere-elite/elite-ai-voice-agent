"""Telnyx webhook handler — dynamic variables + post-call insights.

This is a reference implementation for the two CRM endpoints that
Telnyx needs to power the AI Assistant:

1. POST /api/voice/webhooks/telnyx-init
   Called by Telnyx at the START of every inbound call.
   Receives the caller's phone number, returns account data
   as dynamic variables so the assistant has context immediately.

2. POST /api/voice/webhooks/telnyx-insights
   Called by Telnyx AFTER each call ends.
   Receives structured post-call analysis data for CRM logging.

Deploy this alongside your existing CRM voice endpoints, or
integrate the logic into your existing webhook handler.
"""

from __future__ import annotations

import logging
from aiohttp import web

logger = logging.getLogger("telnyx-webhooks")


# ── 1. Dynamic Variables Webhook ─────────────────────────────────────────
# Telnyx POSTs this at the start of every call. You have <1 second to respond.
# The caller's phone is in payload.telnyx_end_user_target.
#
# Your CRM should look up the account by phone and return the fields below.
# If no account is found, return account_found: "false" and the assistant
# will fall back to manual name+DOB lookup.

async def telnyx_init_handler(request: web.Request) -> web.Response:
    """Handle Telnyx assistant.initialization webhook.

    Expected inbound payload from Telnyx:
    {
      "data": {
        "event_type": "assistant.initialization",
        "payload": {
          "telnyx_end_user_target": "+15551234567",
          "telnyx_agent_target": "+18005551234",
          "telnyx_conversation_channel": "phone_call",
          "call_control_id": "v3:...",
          "assistant_id": "assistant-..."
        }
      }
    }

    Response must return within 1 second.
    """
    body = await request.json()
    payload = body.get("data", {}).get("payload", {})
    caller_phone = payload.get("telnyx_end_user_target", "")

    logger.info("Telnyx init webhook — caller: %s", caller_phone)

    if not caller_phone:
        return web.json_response({
            "dynamic_variables": {"account_found": "false"}
        })

    # ── YOUR CRM LOOKUP HERE ──────────────────────────────────────────
    # Replace this with your actual CRM account lookup by phone.
    # This is the same logic as your existing /tools/lookup-account endpoint.
    #
    # Example using your existing CRM client:
    #
    #   from crm_client import lookup_by_phone
    #   account = await lookup_by_phone(caller_phone)
    #
    # For now, this is a stub that shows the expected response format:

    account = await _lookup_account_by_phone(caller_phone)

    if not account or not account.get("found"):
        return web.json_response({
            "dynamic_variables": {"account_found": "false"}
        })

    # Map CRM fields to Telnyx dynamic variable names
    return web.json_response({
        "dynamic_variables": {
            "account_found": "true",
            "account_id": str(account.get("account_id", "")),
            "elite_id": str(account.get("elite_id", "")),
            "full_name": str(account.get("full_name", "")),
            "first_name": str(account.get("first_name", "")),
            "last_name": str(account.get("last_name", "")),
            "birthdate": str(account.get("dob", "")),
            "phone": str(account.get("phone", "")),
            "email": str(account.get("email", "")),
            "current_balance": str(account.get("current_balance", "")),
            "original_creditor": str(account.get("original_creditor", "")),
            "bank_name": str(account.get("bank_name", "")),
            "charge_off_date": str(account.get("chargeoff_date", "")),
            "portfolio_id": str(account.get("portfolio_id", "")),
            "settlement_open_amount": str(account.get("settlement_open_amount", "")),
            "settlement_floor_amount": str(account.get("settlement_floor_amount", "")),
            "six_payment_amount": str(account.get("six_payment_amount", "")),
            "billing_address_on_file": str(account.get("billing_address_on_file", "")),
            "city": str(account.get("city", "")),
            "state": str(account.get("state", "")),
            "zip": str(account.get("zip", "")),
            "status": str(account.get("status", "")),
            "cease_desist": str(account.get("cease_desist", False)).lower(),
            "has_active_dispute": str(account.get("has_active_dispute", False)).lower(),
        }
    })


async def _lookup_account_by_phone(phone: str) -> dict | None:
    """Stub — replace with your actual CRM lookup.

    This should call the same backend as your existing
    POST /api/voice/tools/lookup-account endpoint.
    """
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://crm.eliteportmgmt.com/api/voice/tools/lookup-account",
            json={"phone_number": phone},
            timeout=aiohttp.ClientTimeout(total=0.8),  # Must respond in <1s
        ) as resp:
            if resp.status == 200:
                return await resp.json()
    return None


# ── 2. Post-Call Insights Webhook ────────────────────────────────────────
# Telnyx sends structured analysis after each call ends.

async def telnyx_insights_handler(request: web.Request) -> web.Response:
    """Handle post-call insights from Telnyx.

    Receives structured fields (payment_promised, resolution_type, etc.)
    plus the formatted call summary for CRM logging.
    """
    body = await request.json()
    logger.info("Telnyx insights webhook received: %s", body)

    # ── YOUR CRM LOGGING HERE ─────────────────────────────────────────
    # Parse the insights and log them to your CRM, same as you do
    # with Retell's call_analyzed webhook today.
    #
    # The payload structure matches your Retell post_call_analysis_data
    # fields: payment_promised, payment_amount, resolution_type, etc.

    return web.json_response({"status": "ok"})


# ── App setup ────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/api/voice/webhooks/telnyx-init", telnyx_init_handler)
    app.router.add_post("/api/voice/webhooks/telnyx-insights", telnyx_insights_handler)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    web.run_app(create_app(), port=8080)
