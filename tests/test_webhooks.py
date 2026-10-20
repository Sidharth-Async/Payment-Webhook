import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from tests.conftest import make_event, post_event, sign


def count(table):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_valid_event_is_stored(client):
    r = post_event(client, make_event())
    assert r.status_code == 200
    assert r.json() == {"status": "processed"}
    assert count("payment_events") == 1
    assert count("payments") == 1


def test_bad_signature_is_rejected(client):
    r = post_event(client, make_event(), signature="wrong")
    assert r.status_code == 401
    assert count("payment_events") == 0


def test_missing_signature_is_rejected(client):
    r = post_event(client, make_event(), signature=False)
    assert r.status_code == 401
    assert count("payment_events") == 0


def test_duplicate_event_is_stored_once(client):
    post_event(client, make_event())
    r = post_event(client, make_event())
    assert r.status_code == 200
    assert r.json() == {"status": "duplicate"}
    assert count("payment_events") == 1


def test_invalid_payload_returns_422(client):
    body = json.dumps({"id": "evt_x"}).encode()
    r = client.post(
        "/webhooks/payments",
        content=body,
        headers={"X-Signature": sign(body), "Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_concurrent_duplicates_store_one_row():
    for round_no in range(20):
        event = make_event(event_id=f"evt_race_{round_no}")
        barrier = Barrier(2)

        def send():
            c = TestClient(app)
            barrier.wait()
            return post_event(c, event).json()["status"]

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: send(), range(2)))

        assert sorted(results) == ["duplicate", "processed"]

    assert count("payment_events") == 20