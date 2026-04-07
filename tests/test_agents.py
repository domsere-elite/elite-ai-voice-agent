"""Tests for Elite Voice Agent conversation flow.

These tests verify the business logic, waterfall calculations, and
agent handoff routing without requiring a live LiveKit connection.
"""

from __future__ import annotations

import pytest

from models import UserData, AccountData
from agents.waterfall import _hardship_terms
from agents.greeting import _populate_account


# ── Hardship calculation tests ──────────────────────────────────────────

class TestHardshipTerms:
    def test_under_750(self):
        months, minimum = _hardship_terms(500)
        assert months == 12
        assert minimum == 65.0

    def test_750_to_1999(self):
        months, minimum = _hardship_terms(1500)
        assert months == 18
        assert minimum == 115.0

    def test_2000_to_3499(self):
        months, minimum = _hardship_terms(2500)
        assert months == 24
        assert minimum == 150.0

    def test_3500_to_4999(self):
        months, minimum = _hardship_terms(4000)
        assert months == 27
        assert minimum == 190.0

    def test_5000_plus(self):
        months, minimum = _hardship_terms(6000)
        assert months == 30
        # 6000/30 = 200 → ceil to nearest 10 = 200
        assert minimum == 200.0

    def test_5000_plus_rounds_up(self):
        months, minimum = _hardship_terms(7500)
        assert months == 30
        # 7500/30 = 250 → ceil to nearest 10 = 250
        assert minimum == 250.0

    def test_5000_plus_rounds_up_partial(self):
        months, minimum = _hardship_terms(6100)
        assert months == 30
        # 6100/30 ≈ 203.33 → ceil to nearest 10 = 210
        assert minimum == 210.0

    def test_boundary_750(self):
        months, minimum = _hardship_terms(750)
        assert months == 18
        assert minimum == 115.0

    def test_boundary_2000(self):
        months, minimum = _hardship_terms(2000)
        assert months == 24
        assert minimum == 150.0

    def test_boundary_3500(self):
        months, minimum = _hardship_terms(3500)
        assert months == 27
        assert minimum == 190.0

    def test_boundary_5000(self):
        months, minimum = _hardship_terms(5000)
        assert months == 30
        # 5000/30 ≈ 166.67 → ceil to nearest 10 = 170 but floor is 200
        assert minimum == 200.0


# ── Account population tests ───────────────────────────────────────────

class TestPopulateAccount:
    def test_populates_all_fields(self):
        ud = UserData()
        data = {
            "found": True,
            "account_id": "ACC-001",
            "elite_id": "ELT-001",
            "full_name": "John Doe",
            "first_name": "John",
            "last_name": "Doe",
            "dob": "01/15/1985",
            "current_balance": "2500.00",
            "original_creditor": "Bank of Test",
            "settlement_open_amount": "1500.00",
            "settlement_floor_amount": "1000.00",
            "six_payment_amount": "416.67",
            "cease_desist": False,
            "has_active_dispute": False,
        }
        _populate_account(ud, data)

        assert ud.account.found is True
        assert ud.account.account_id == "ACC-001"
        assert ud.account.full_name == "John Doe"
        assert ud.account.current_balance == "2500.00"
        assert ud.account.settlement_open_amount == "1500.00"
        assert ud.account.cease_desist is False

    def test_handles_missing_fields(self):
        ud = UserData()
        _populate_account(ud, {"found": False})

        assert ud.account.found is False
        assert ud.account.account_id == ""
        assert ud.account.full_name == ""

    def test_cease_desist_flag(self):
        ud = UserData()
        _populate_account(ud, {"found": True, "cease_desist": True})
        assert ud.account.cease_desist is True

    def test_active_dispute_flag(self):
        ud = UserData()
        _populate_account(ud, {"found": True, "has_active_dispute": True})
        assert ud.account.has_active_dispute is True


# ── UserData state management tests ────────────────────────────────────

class TestUserData:
    def test_default_state(self):
        ud = UserData()
        assert ud.identity_verified is False
        assert ud.compliance_delivered is False
        assert ud.accepted_option == ""
        assert ud.payment_amount == 0.0
        assert ud.is_multi_payment is False

    def test_payment_state_tracking(self):
        ud = UserData()
        ud.accepted_option = "B"
        ud.payment_amount = 2500.0
        ud.is_multi_payment = True
        ud.plan_months = 6
        ud.monthly_amount = 416.67
        ud.payment_type = "arrangement"

        assert ud.accepted_option == "B"
        assert ud.is_multi_payment is True
        assert ud.plan_months == 6

    def test_billing_address(self):
        ud = UserData()
        ud.billing_street = "123 Main St"
        ud.billing_city = "Miami"
        ud.billing_state = "FL"
        ud.billing_zip = "33101"
        ud.address_confirmed = True

        assert ud.address_confirmed is True
        assert ud.billing_state == "FL"
