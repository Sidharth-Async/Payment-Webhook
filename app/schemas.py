from pydantic import BaseModel

class PaymentData(BaseModel):
    payment_id: str
    amount_cents: int
    currency: str

class WebhookEvent(BaseModel):
    id: str
    type: str
    data: PaymentData