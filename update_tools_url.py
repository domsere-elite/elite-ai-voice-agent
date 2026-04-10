"""Update all assistant webhook tool URLs to a new base URL."""
import json
import os
import urllib.request
import ssl
import sys

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ["TELNYX_API_KEY"]
ASSISTANT_ID = os.environ.get("TELNYX_ASSISTANT_ID", "assistant-6c04465e-3c71-4035-9ed3-a6943bbf3699")

OLD_BASE = "https://crm.eliteportmgmt.com"
NEW_BASE = sys.argv[1] if len(sys.argv) > 1 else "https://branden-fumiest-vendibly.ngrok-free.dev"

# 1. GET current assistant
ctx = ssl.create_default_context()
req = urllib.request.Request(
    f"https://api.telnyx.com/v2/ai/assistants/{ASSISTANT_ID}",
    headers={"Authorization": f"Bearer {API_KEY}"},
)
with urllib.request.urlopen(req, context=ctx) as resp:
    assistant = json.loads(resp.read().decode("utf-8"))

# 2. Update tool URLs
tools = assistant.get("tools", [])
changed = 0
for tool in tools:
    if tool.get("type") == "webhook":
        wh = tool.get("webhook", {})
        url = wh.get("url", "")
        if OLD_BASE in url:
            wh["url"] = url.replace(OLD_BASE, NEW_BASE)
            changed += 1
            print(f"  {wh['name']}: {url} -> {wh['url']}")

if not changed:
    # Check if already using ngrok, swap back
    for tool in tools:
        if tool.get("type") == "webhook":
            wh = tool.get("webhook", {})
            url = wh.get("url", "")
            if NEW_BASE not in url and "ngrok" in url:
                wh["url"] = url.replace(url.split("/api")[0], NEW_BASE)
                changed += 1
                print(f"  {wh['name']}: -> {wh['url']}")

print(f"\nUpdated {changed} tool URLs")

# 3. PATCH assistant
payload = {"tools": tools}
data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    f"https://api.telnyx.com/v2/ai/assistants/{ASSISTANT_ID}",
    data=data,
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    method="PATCH",
)
try:
    with urllib.request.urlopen(req, context=ctx) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        print(f"Assistant updated successfully. ID: {result['id']}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8")
    print(f"HTTP {e.code}: {body[:500]}")
