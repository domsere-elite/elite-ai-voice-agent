"""Mock CRM + Call Control webhook handler for testing the Telnyx AI Assistant.

Run:  python start_mock.py

Handles:
1. Call Control webhooks (answer call → start AI assistant)
2. All 7 CRM tool endpoints (return mock success responses)
"""

import json
import logging
import os
import threading
import ssl
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pyngrok import ngrok
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("mock-crm")

PORT = 8099
API_KEY = os.environ["TELNYX_API_KEY"]
ASSISTANT_ID = os.environ.get("TELNYX_ASSISTANT_ID", "assistant-6c04465e-3c71-4035-9ed3-a6943bbf3699")

# ── Mock CRM responses ──────────────────────────────────────────────────

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

CRM_ROUTES = {
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


# ── Telnyx Call Control helpers ──────────────────────────────────────────

def telnyx_api(endpoint, payload):
    """POST to Telnyx Call Control API."""
    url = f"https://api.telnyx.com/v2{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            log.info("  Telnyx API %s -> OK", endpoint)
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        log.error("  Telnyx API %s -> HTTP %d: %s", endpoint, e.code, body[:300])
        return None


def handle_call_control(body):
    """Handle Telnyx Call Control webhook events."""
    data = body.get("data", {})
    event_type = data.get("event_type", "")
    payload = data.get("payload", {})
    call_control_id = payload.get("call_control_id", "")

    log.info("  Call Control event: %s (call_control_id=%s)", event_type, call_control_id[:20])

    if event_type == "call.initiated":
        direction = payload.get("direction", "")
        if direction == "incoming":
            log.info("  --> Answering inbound call...")
            telnyx_api(f"/calls/{call_control_id}/actions/answer", {})

    elif event_type == "call.answered":
        log.info("  --> Starting AI Assistant: %s", ASSISTANT_ID)
        telnyx_api(f"/calls/{call_control_id}/actions/ai_assistant_start", {
            "id": ASSISTANT_ID,
        })

    elif event_type == "call.hangup":
        log.info("  --> Call ended. Cause: %s", payload.get("hangup_cause", "unknown"))

    elif event_type == "call.conversation.ended":
        log.info("  --> AI conversation ended.")

    else:
        log.info("  --> Unhandled event: %s", event_type)

    return {"status": "ok"}


# ── HTTP Server ──────────────────────────────────────────────────────────

class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        body = json.loads(raw) if raw else {}

        log.info("POST %s", self.path)

        if self.path == "/api/voice/texml-inbound":
            # Return TeXML that starts the AI assistant
            log.info("  --> TeXML inbound webhook, starting AI assistant")
            texml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <AI assistantId="{ASSISTANT_ID}" />
    </Connect>
</Response>"""
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(texml.encode())
            return
        elif self.path == "/api/voice/call-control":
            resp = handle_call_control(body)
            self.send_response(200)
        elif self.path in CRM_ROUTES:
            resp = CRM_ROUTES[self.path](body)
            log.info("  CRM mock -> %s", json.dumps(resp)[:150])
            self.send_response(200)
        else:
            resp = {"error": f"Unknown route: {self.path}"}
            log.warning("  404: %s", self.path)
            self.send_response(404)

        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode())

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Mock CRM + Call Control handler running.")

    def log_message(self, *args):
        pass


def run_server():
    server = HTTPServer(("0.0.0.0", PORT), MockHandler)
    server.serve_forever()


if __name__ == "__main__":
    # Start HTTP server in background thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    log.info("Mock server running on http://localhost:%d", PORT)

    # Open ngrok tunnel
    # Try to connect ngrok, but if tunnel already exists, just use it
    public_url = None
    try:
        ngrok.kill()
        import time as _t; _t.sleep(2)
        tunnel = ngrok.connect(PORT, "http")
        public_url = tunnel.public_url
    except Exception as e:
        log.warning("Ngrok tunnel failed (may already exist): %s", e)
        public_url = "https://branden-fumiest-vendibly.ngrok-free.dev"
        log.info("Using existing tunnel: %s", public_url)
    log.info("")
    log.info("=" * 60)
    log.info("  NGROK PUBLIC URL: %s", public_url)
    log.info("=" * 60)
    log.info("")
    log.info("Waiting for calls to +13464061576...")
    log.info("Press Ctrl+C to stop.")

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        ngrok.disconnect(tunnel.public_url)
