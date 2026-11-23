from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel


class StartPaymentRequest(BaseModel):
    cart_id: UUID
    customer_id: UUID
    amount: Decimal
    currency: str


class ProvideCardDetailsRequest(BaseModel):
    card_number: str


class SelectPaymentMethodRequest(BaseModel):
    method: Literal["CARD", "BLIK"]


class ProcessPaymentRequest(BaseModel):
    blik_code: str | None = None
