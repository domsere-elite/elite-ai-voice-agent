"""Create the Telnyx AI Assistant via the API."""
import json
import os
import urllib.request
import ssl
import sys

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ["TELNYX_API_KEY"]

with open("telnyx_assistant_config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

instructions = config["instructions"]
greeting = config["greeting"]

payload = {
    "name": "EPM Inbound - Erik",
    "instructions": instructions,
    "greeting": greeting,
    "model": "anthropic/claude-haiku-4-5",
    "dynamic_variables_webhook_url": "https://crm.eliteportmgmt.com/api/voice/webhooks/telnyx-init",
    "telephony_settings": {
        "noise_suppression": "krisp"
    },
    "tools": [
        {
            "type": "webhook",
            "webhook": {
                "name": "findAccountByPhone",
                "description": "Look up account by name and date of birth when phone auto-lookup failed.",
                "url": "https://crm.eliteportmgmt.com/api/voice/tools/lookup-account",
                "method": "POST",
                "parameters": [
                    {"name": "full_name", "type": "string", "description": "Caller full name.", "required": True},
                    {"name": "dob", "type": "string", "description": "Caller date of birth.", "required": True}
                ]
            }
        },
        {
            "type": "webhook",
            "webhook": {
                "name": "deliverCompliance",
                "description": "Log that the Mini Miranda compliance disclosure was delivered.",
                "url": "https://crm.eliteportmgmt.com/api/voice/tools/log-compliance",
                "method": "POST",
                "parameters": [
                    {"name": "event", "type": "string", "description": "Always mini_miranda_delivered.", "required": True},
                    {"name": "account_id", "type": "string", "description": "The account ID.", "required": True},
                    {"name": "execution_message", "type": "string", "description": "The exact Mini Miranda text.", "required": True}
                ]
            }
        },
        {
            "type": "webhook",
            "webhook": {
                "name": "processLivePayment",
                "description": "Process an immediate live card charge.",
                "url": "https://crm.eliteportmgmt.com/api/voice/tools/process-payment",
                "method": "POST",
                "parameters": [
                    {"name": "account_id", "type": "string", "required": True},
                    {"name": "amount", "type": "number", "description": "Dollar amount to charge.", "required": True},
                    {"name": "payment_type", "type": "string", "description": "full_balance or settlement.", "required": True},
                    {"name": "card_number", "type": "string", "required": True},
                    {"name": "exp_month", "type": "string", "required": True},
                    {"name": "exp_year", "type": "string", "required": True},
                    {"name": "cvv", "type": "string", "required": True},
                    {"name": "cardholder_name", "type": "string", "required": True},
                    {"name": "elite_id", "type": "string", "required": True},
                    {"name": "billing_address", "type": "string", "required": True},
                    {"name": "billing_street", "type": "string", "required": True},
                    {"name": "billing_city", "type": "string", "required": True},
                    {"name": "billing_state", "type": "string", "required": True},
                    {"name": "billing_zip", "type": "string", "required": True},
                    {"name": "address_on_file_confirmed", "type": "boolean", "required": True}
                ]
            }
        },
        {
            "type": "webhook",
            "webhook": {
                "name": "tokenizeCard",
                "description": "Tokenize card securely for multi-payment arrangements.",
                "url": "https://crm.eliteportmgmt.com/api/voice/tools/tokenize-card",
                "method": "POST",
                "parameters": [
                    {"name": "account_id", "type": "string", "required": True},
                    {"name": "billing_address", "type": "string", "required": False}
                ]
            }
        },
        {
            "type": "webhook",
            "webhook": {
                "name": "confirmPaymentArrangement",
                "description": "Confirm a multi-payment arrangement with tokenized card.",
                "url": "https://crm.eliteportmgmt.com/api/voice/tools/confirm-arrangement",
                "method": "POST",
                "parameters": [
                    {"name": "account_id", "type": "string", "required": True},
                    {"name": "tokenized_card_id", "type": "string", "required": True},
                    {"name": "first_payment_date", "type": "string", "required": True},
                    {"name": "first_payment_amount", "type": "string", "required": True},
                    {"name": "recurring_payment_amount", "type": "string", "required": False},
                    {"name": "recurring_day_of_month", "type": "string", "required": False}
                ]
            }
        },
        {
            "type": "webhook",
            "webhook": {
                "name": "logDispute",
                "description": "Log a dispute declaration from the caller.",
                "url": "https://crm.eliteportmgmt.com/api/voice/tools/log-dispute",
                "method": "POST",
                "parameters": [
                    {"name": "account_id", "type": "string", "required": True},
                    {"name": "dispute_reason", "type": "string", "required": False}
                ]
            }
        },
        {
            "type": "webhook",
            "webhook": {
                "name": "logCeaseAndDesist",
                "description": "Log a cease and desist request.",
                "url": "https://crm.eliteportmgmt.com/api/voice/tools/log-cnd",
                "method": "POST",
                "parameters": [
                    {"name": "account_id", "type": "string", "required": True},
                    {"name": "note", "type": "string", "required": False}
                ]
            }
        },
        {"type": "hangup", "hangup": {"name": "hangup", "description": "End the call when the conversation is complete."}},
        {
            "type": "transfer",
            "transfer": {
                "name": "transferToSpecialist",
                "description": "Transfer the call to a live specialist.",
                "number": "+18333814416"
            }
        }
    ]
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    "https://api.telnyx.com/v2/ai/assistants",
    data=data,
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    },
    method="POST"
)

ctx = ssl.create_default_context()
try:
    with urllib.request.urlopen(req, context=ctx) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        print(json.dumps(result, indent=2))
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8")
    print(f"HTTP {e.code}:")
    try:
        print(json.dumps(json.loads(body), indent=2))
    except Exception:
        print(body)
