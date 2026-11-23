from dataclasses import dataclass
from typing import Protocol
from app.domain.value_objects import BlikCode, CardNumber, GatewayTransactionId, Money, PaymentId


@dataclass(frozen=True)
class GatewayResult:
    approved: bool
    transaction_id: GatewayTransactionId | None = None
    decline_reason: str | None = None


class CardNetwork(Protocol):
    """External System: Card Network / Bank Issuer System.

    Every call passes the PaymentId as an idempotency key, so a retried or concurrent
    request can never charge the customer twice.
    """

    def authorize(self, payment_id: PaymentId, card: CardNumber, amount: Money) -> GatewayResult: ...

    def capture(
        self, payment_id: PaymentId, authorization_id: GatewayTransactionId, amount: Money
    ) -> GatewayResult: ...


class BlikPaymentGateway(Protocol):
    """External System: BLIK Payment. PaymentId is the idempotency key."""

    def charge(self, payment_id: PaymentId, code: BlikCode, amount: Money) -> GatewayResult: ...
