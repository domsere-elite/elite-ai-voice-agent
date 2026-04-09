"""HTTP client for Elite Portfolio Management CRM voice-tool endpoints."""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger("elite-agent.crm")

CRM_BASE = os.getenv("CRM_BASE_URL", "https://crm.eliteportmgmt.com/api/voice")

_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    """Return a shared aiohttp session (lazily created, reuses connections)."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
        )
    return _session


async def _post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Fire a POST to the CRM and return the JSON response."""
    url = f"{CRM_BASE}/{endpoint}"
    logger.info("CRM POST %s  payload_keys=%s", url, list(payload.keys()))
    session = _get_session()
    async with session.post(url, json=payload) as resp:
        body = await resp.json()
        logger.info("CRM %s → %s", resp.status, body.get("found", "ok"))
        return body


# ── Account lookup ──────────────────────────────────────────────────────

async def lookup_by_phone(phone: str) -> dict[str, Any]:
    return await _post("tools/lookup-account", {"phone_number": phone})


async def lookup_by_name(full_name: str, dob: str) -> dict[str, Any]:
    return await _post("tools/lookup-account", {"full_name": full_name, "dob": dob})


# ── Compliance ──────────────────────────────────────────────────────────

MINI_MIRANDA = (
    "This call may be recorded for quality and compliance purposes. "
    "This is a communication from a debt collector. "
    "This is an attempt to collect a debt, and any information obtained "
    "will be used for that purpose."
)


async def log_compliance(account_id: str) -> dict[str, Any]:
    return await _post("tools/log-compliance", {
        "event": "mini_miranda_delivered",
        "account_id": account_id,
        "execution_message": MINI_MIRANDA,
    })


# ── Payment processing ─────────────────────────────────────────────────

async def process_payment(
    *,
    account_id: str,
    amount: float,
    payment_type: str,
    card_number: str,
    exp_month: str,
    exp_year: str,
    cvv: str,
    cardholder_name: str,
    elite_id: str,
    billing_address: str,
    billing_street: str,
    billing_city: str,
    billing_state: str,
    billing_zip: str,
    address_on_file_confirmed: bool,
) -> dict[str, Any]:
    return await _post("tools/process-payment", {
        "account_id": account_id,
        "amount": amount,
        "payment_type": payment_type,
        "card_number": card_number,
        "exp_month": exp_month,
        "exp_year": exp_year,
        "cvv": cvv,
        "cardholder_name": cardholder_name,
        "elite_id": elite_id,
        "billing_address": billing_address,
        "billing_street": billing_street,
        "billing_city": billing_city,
        "billing_state": billing_state,
        "billing_zip": billing_zip,
        "address_on_file_confirmed": address_on_file_confirmed,
    })


async def tokenize_card(account_id: str, billing_address: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"account_id": account_id}
    if billing_address:
        payload["billing_address"] = billing_address
    return await _post("tools/tokenize-card", payload)


async def confirm_arrangement(
    *,
    account_id: str,
    tokenized_card_id: str,
    first_payment_date: str,
    first_payment_amount: str,
    recurring_payment_amount: str = "",
    recurring_day_of_month: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "account_id": account_id,
        "tokenized_card_id": tokenized_card_id,
        "first_payment_date": first_payment_date,
        "first_payment_amount": first_payment_amount,
    }
    if recurring_payment_amount:
        payload["recurring_payment_amount"] = recurring_payment_amount
    if recurring_day_of_month:
        payload["recurring_day_of_month"] = recurring_day_of_month
    return await _post("tools/confirm-arrangement", payload)


# ── Dispute / CND ──────────────────────────────────────────────────────

async def log_dispute(account_id: str, reason: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"account_id": account_id}
    if reason:
        payload["dispute_reason"] = reason
    return await _post("tools/log-dispute", payload)


async def log_cease_and_desist(account_id: str, note: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"account_id": account_id}
    if note:
        payload["note"] = note
    return await _post("tools/log-cnd", payload)
