"""Lightweight mock CRM server for testing the Telnyx AI Assistant.

Run with:  python mock_crm.py

Exposes all 7 CRM endpoints on port 8099 and returns realistic
success responses without touching production data.
"""

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("mock-crm")

MOCK_ACCOUNT = {
    "found": True,
    "account_id": "TEST-98765",
    "elite_id": "EPM-11111",
    "full_name": "Michael Johnson",
    "first_name": "Michael",
    "last_name": "Johnson",
    "dob": "June 15, 1988",
    "phone": "+13465551234",
    "email": "mjohnson@email.com",
    "current_balance": "1715",
    "original_creditor": "National Credit Services",
    "bank_name": "Chase",
    "chargeoff_date": "December 9, 2025",
    "portfolio_id": "GLD",
    "settlement_open_amount": "1200",
    "settlement_floor_amount": "900",
    "six_payment_amount": "285.83",
    "billing_address_on_file": "4521 Westheimer Road",
    "city": "Houston",
    "state": "TX",
    "zip": "77027",
    "status": "active",
    "cease_desist": False,
    "has_active_dispute": False,
}

ROUTES = {
    "/api/voice/tools/lookup-account": lambda body: MOCK_ACCOUNT,
    "/api/voice/tools/log-compliance": lambda body: {"success": True, "message": "Compliance logged (mock)"},
    "/api/voice/tools/process-payment": lambda body: {
        "success": True,
        "transaction_id": "TXN-MOCK-00001",
        "message": f"Payment of ${body.get('amount', 0)} processed successfully (mock)",
    },
    "/api/voice/tools/tokenize-card": lambda body: {
        "success": True,
        "tokenized_card_id": "tok_mock_abc123",
        "message": "Card tokenized (mock)",
    },
    "/api/voice/tools/confirm-arrangement": lambda body: {
        "success": True,
        "arrangement_id": "ARR-MOCK-00001",
        "message": "Arrangement confirmed (mock)",
    },
    "/api/voice/tools/log-dispute": lambda body: {"success": True, "message": "Dispute logged (mock)"},
    "/api/voice/tools/log-cnd": lambda body: {"success": True, "message": "Cease and desist logged (mock)"},
}


class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        body = json.loads(raw) if raw else {}

        log.info("POST %s  body=%s", self.path, json.dumps(body)[:200])

        handler = ROUTES.get(self.path)
        if handler:
            resp = handler(body)
            self.send_response(200)
        else:
            resp = {"error": f"Unknown route: {self.path}"}
            self.send_response(404)

        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode())
        log.info("  → %s", json.dumps(resp)[:200])

    def log_message(self, *args):
        pass  # suppress default logging


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8099), MockHandler)
    log.info("Mock CRM running on http://localhost:8099")
    log.info("Routes: %s", ", ".join(ROUTES.keys()))
    server.serve_forever()
