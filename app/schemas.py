from pydantic import BaseModel
from datetime import datetime
from pydantic import ConfigDict

class PaymentData(BaseModel):
    payment_id: str
    amount_cents: int
    currency: str

class WebhookEvent(BaseModel):
    id: str
    type: str
    data: PaymentData

class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    external_payment_id: str
    amount_cents: int
    currency: str
    status: str
    updated_at: datetime