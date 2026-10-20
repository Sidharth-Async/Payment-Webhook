import os

# Must be set BEFORE the app is imported, because settings load at import time.
os.environ["DATABASE_URL"] = "postgresql+psycopg://webhook_dev:passw123@localhost:5433/webhooks_test"
os.environ["WEBHOOK_SECRET"] = "test_secret"

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import Base, engine
from app.main import app

SECRET = "test_secret"

@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE payment_events, payments RESTART IDENTITY"))
    yield

@pytest.fixture
def client():
    return TestClient(app)

def make_event(event_id="evt_1", event_type="payment.succeeded", payment_id="pay_1"):
    return {
        "id": event_id,
        "type": event_type,
        "data": {"payment_id": payment_id, "amount_cents": 15000, "currency": "EUR"},
    }

def sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

def post_event(client, event, signature=None):
    body = json.dumps(event).encode()
    headers = {"Content-Type": "application/json"}
    if signature is not False:
        headers["X-Signature"] = signature or sign(body)
    return client.post("/webhooks/payments", content=body, headers=headers)