"""Shared data models passed between agents via AgentSession[UserData]."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AccountData:
    """Fields returned by the CRM account-lookup endpoints."""

    account_id: str = ""
    elite_id: str = ""
    full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    dob: str = ""
    phone: str = ""
    email: str = ""
    current_balance: str = ""
    original_creditor: str = ""
    bank_name: str = ""
    chargeoff_date: str = ""
    portfolio_id: str = ""
    settlement_open_amount: str = ""
    settlement_floor_amount: str = ""
    six_payment_amount: str = ""
    billing_address_on_file: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    status: str = ""
    original_account_number: str = ""
    cease_desist: bool = False
    has_active_dispute: bool = False
    found: bool = False


@dataclass
class UserData:
    """Session-wide state shared across all agents."""

    # LiveKit room info (set once in entrypoint)
    room_name: str = ""
    participant_identity: str = ""

    # Caller metadata
    caller_phone: str = ""

    # Account (populated after lookup)
    account: AccountData = field(default_factory=AccountData)

    # Flow flags
    identity_verified: bool = False
    compliance_delivered: bool = False

    # Payment capture
    accepted_option: str = ""          # A | B | C | D | E
    payment_amount: float = 0.0
    payment_type: str = ""             # full_balance | settlement | arrangement
    is_multi_payment: bool = False
    plan_months: int = 0
    monthly_amount: float = 0.0
    first_payment_date: str = ""

    # Billing address (collected or confirmed during payment)
    billing_street: str = ""
    billing_city: str = ""
    billing_state: str = ""
    billing_zip: str = ""
    address_confirmed: bool = False
