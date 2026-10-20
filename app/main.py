import json

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Payment, PaymentEvent
from app.schemas import WebhookEvent
from app.security import verify_signature

app = FastAPI(title="Payment Webhook Service")

STATUS_BY_TYPE = {
    "payment.succeeded": "succeeded",
    "payment.failed": "failed",
    "payment.refunded": "refunded",
}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/webhooks/payments")
async def receive_webhook(
    request: Request,
    x_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    raw = await request.body()

    if not x_signature or not verify_signature(raw, x_signature, settings.webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        event = WebhookEvent.model_validate_json(raw)
    except ValidationError:
        raise HTTPException(status_code=422, detail="Invalid payload")

    status = STATUS_BY_TYPE.get(event.type)
    if status is None:
        raise HTTPException(status_code=422, detail=f"Unknown event type: {event.type}")

    # Duplicate-proof insert: the database decides who wins
    stmt = (
        insert(PaymentEvent)
        .values(event_id=event.id, event_type=event.type, payload=json.loads(raw))
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(PaymentEvent.id)
    )
    inserted_id = db.execute(stmt).scalar_one_or_none()
    if inserted_id is None:
        return {"status": "duplicate"}  # still 200, so the sender stops retrying

    # Update the payment in the same transaction as the event
    upsert = insert(Payment).values(
        external_payment_id=event.data.payment_id,
        amount_cents=event.data.amount_cents,
        currency=event.data.currency,
        status=status,
    )
    upsert = upsert.on_conflict_do_update(
        index_elements=["external_payment_id"],
        set_={"status": status, "updated_at": func.now()},
    )
    db.execute(upsert)
    db.commit()
    return {"status": "processed"}