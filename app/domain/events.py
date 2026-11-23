from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class DomainEvent:
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc), kw_only=True)


@dataclass(frozen=True)
class CreditCardDetailsProvided(DomainEvent):
    payment_id: UUID
    masked_card_number: str
    card_brand: str


@dataclass(frozen=True)
class CreditCardValidated(DomainEvent):
    payment_id: UUID
    authorization_id: str


@dataclass(frozen=True)
class PaymentMethodSelected(DomainEvent):
    payment_id: UUID
    method: str


@dataclass(frozen=True)
class PaymentProcessedSuccessfully(DomainEvent):
    """Triggers the Inventory Allocation Policy (Reserve inventory) and Place order."""

    payment_id: UUID
    cart_id: UUID
    customer_id: UUID
    amount: Decimal
    currency: str
    method: str
    gateway_transaction_id: str


@dataclass(frozen=True)
class PaymentRejected(DomainEvent):
    payment_id: UUID
    cart_id: UUID
    customer_id: UUID
    method: str
    reason: str
