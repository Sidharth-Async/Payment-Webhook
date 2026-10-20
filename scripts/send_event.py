import hashlib
import hmac
import json
import sys

import httpx

SECRET = "web123"
event_id = sys.argv[1] if len(sys.argv) > 1 else "evt_1"

event = {
    "id": event_id,
    "type": "payment.succeeded",
    "data": {"payment_id": "pay_1", "amount_cents": 15000, "currency": "EUR"},
}
body = json.dumps(event).encode()
signature = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

r = httpx.post(
    "http://127.0.0.1:8000/webhooks/payments",
    content=body,
    headers={"X-Signature": signature, "Content-Type": "application/json"},
)
print(r.status_code, r.json())