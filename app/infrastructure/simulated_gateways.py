"""Stand-ins for the external systems until real integrations exist.

Transaction ids are derived from the PaymentId (the idempotency key), so repeating a call
returns the same id instead of creating a second charge.
"""

from decimal import Decimal
from app.application.gateways import GatewayResult
from app.domain.value_objects import BlikCode, CardNumber, GatewayTransactionId, Money, PaymentId

CARD_LIMIT = Decimal("10000.00")
DECLINED_BLIK_CODE = "000000"


class SimulatedCardNetwork:
    def authorize(self, payment_id: PaymentId, card: CardNumber, amount: Money) -> GatewayResult:
        if amount.amount > CARD_LIMIT:
            return GatewayResult(approved=False, decline_reason="insufficient funds")
        return GatewayResult(True, GatewayTransactionId(f"card-auth-{payment_id.value.hex}"))

    def capture(
        self, payment_id: PaymentId, authorization_id: GatewayTransactionId, amount: Money
    ) -> GatewayResult:
        return GatewayResult(True, GatewayTransactionId(f"card-cap-{payment_id.value.hex}"))


class SimulatedBlikGateway:
    def charge(self, payment_id: PaymentId, code: BlikCode, amount: Money) -> GatewayResult:
        if code.value == DECLINED_BLIK_CODE:
            return GatewayResult(approved=False, decline_reason="BLIK code rejected by the bank")
        return GatewayResult(True, GatewayTransactionId(f"blik-{payment_id.value.hex}"))
