from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class PaymentSummaryDto:
    """Read model: Payment Summary. Contains the masked card number only."""

    payment_id: UUID
    cart_id: UUID
    customer_id: UUID
    amount: Decimal
    currency: str
    status: str
    method: str | None
    masked_card_number: str | None
    card_brand: str | None
    gateway_transaction_id: str | None
    rejection_reason: str | None


@dataclass(frozen=True)
class PaymentOptionsDto:
    """Read model: Available Payment Options."""

    payment_id: UUID
    available_methods: tuple[str, ...]
