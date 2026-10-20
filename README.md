# Payment Webhook Service

![tests](https://github.com/Sidharth-Async/Payment-Webhook/actions/workflows/tests.yml/badge.svg)

A small FastAPI service that receives payment events from a provider, checks that they are genuine, stores each event exactly once, and keeps a payment record up to date.

The sender in this repo is simulated (`scripts/send_event.py`). It uses an HMAC signature like many real providers do, but it is not Stripe or any other real provider.

## The problem

Payment providers retry webhooks when a delivery looks like it failed, so the same event can arrive more than once, sometimes at the same moment. If every copy is processed, a payment can be recorded twice. This service makes sure it is recorded once.

## How it works

For each `POST /webhooks/payments`:

1. **Read the raw body.** The signature is computed over the exact bytes that were sent, so the body is verified before any JSON parsing.
2. **Verify the signature.** HMAC-SHA256 with a shared secret, compared in constant time. A missing or wrong signature returns `401` and nothing is stored.
3. **Validate the payload** with Pydantic. A malformed payload returns `422`.
4. **Insert the event with a unique `event_id`**, using `INSERT ... ON CONFLICT DO NOTHING`. The database decides which request wins, so two identical events arriving together cannot both be stored.
5. **Return `200` for duplicates.** The sender stops retrying, and no second row is written.
6. **Update the payment in the same commit** as the event, so an event is never stored without its payment update.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/webhooks/payments` | Receive a signed payment event |
| GET | `/payments` | List payments (optional `?status=` filter) |
| GET | `/payments/{id}` | Get one payment |
| GET | `/health` | Health check |

Interactive docs are served at `/docs`.

Handled event types: `payment.succeeded`, `payment.failed`, `payment.refunded`.

## Run it

```bash
cp .env.example .env
docker compose up --build
python scripts/send_event.py evt_1    # {"status": "processed"}
python scripts/send_event.py evt_1    # {"status": "duplicate"}
```

For local development without Docker for the API:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db
alembic upgrade head
fastapi dev app/main.py
```

## Tests

```bash
python -m pytest -v
```

The tests run against a real PostgreSQL database, not an in-memory one, because concurrent inserts behave differently there. They cover:

- a valid event is stored
- a bad signature is rejected, and nothing is stored
- a missing signature is rejected
- a duplicate event is stored once
- an invalid payload returns `422`
- **concurrency:** two requests with the same event ID are sent at the same instant, repeated for 20 rounds. Exactly one is processed and the other is reported as a duplicate each time.

The concurrent test is probabilistic. A pass means no failure in 20 rounds, not a proof.

GitHub Actions runs the suite on every push against a Postgres service container.

## Stack

Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, pytest, Docker, GitHub Actions.

## Design notes and known limits

- **Database over code for duplicates.** A "check, then insert" in application code leaves a gap when two requests arrive together. The unique constraint closes it.
- **Simulated sender.** Real providers have their own signature formats and header names, so a real integration needs those details.
- **No replay protection yet.** A signed event could be re-sent later. Adding a signed timestamp and rejecting old ones is the next step.
- **Out-of-order events.** A status-priority rule stops an older event from overwriting a later one, but it is a heuristic. A provider timestamp or sequence number would be more reliable.
- **Read endpoints are unauthenticated.** Fine for a demo, not for production.
- **Development secrets** in `docker-compose.yml` and the workflow are throwaway values. Use real secrets from the environment in any real deployment.

## What I learned

This is a Python rebuild of the idempotency approach I used in my Java project, [remitlytics-core](https://github.com/Sidharth-Async/remitlytics-core). (Remitlytics isn't just another CRUD API. It is a strictly structured financial engine designed to handle invoice lifecycles, guarantee transaction integrity via a double-entry ledger, and communicate with the outside world through a fully decoupled, async webhook pipeline.)
