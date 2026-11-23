from datetime import datetime, timezone
from typing import Any
from sqlmodel import Session, update
from app.application.exceptions import ConcurrentModificationException
from app.domain.aggregates import Payment, PaymentStatus
from app.domain.value_objects import (
    CartId,
    CustomerId,
    GatewayTransactionId,
    MaskedCardNumber,
    Money,
    PaymentId,
    PaymentMethod,
)
from app.infrastructure.models import PaymentTable


class PostgresPaymentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, payment_id: PaymentId) -> Payment | None:
        row = self._session.get(PaymentTable, payment_id.value, populate_existing=True)
        if row is None or row.is_deleted:
            return None
        return Payment(
            id=PaymentId(row.id),
            cart_id=CartId(row.cart_id),
            customer_id=CustomerId(row.customer_id),
            amount=Money(row.amount, row.currency),
            _status=PaymentStatus(row.status),
            _method=PaymentMethod(row.method) if row.method else None,
            _masked_card=MaskedCardNumber(row.masked_card_number) if row.masked_card_number else None,
            _card_brand=row.card_brand,
            _authorization_id=GatewayTransactionId(row.authorization_id) if row.authorization_id else None,
            _gateway_transaction_id=(
                GatewayTransactionId(row.gateway_transaction_id) if row.gateway_transaction_id else None
            ),
            _rejection_reason=row.rejection_reason,
            version=row.version,
        )

    def save(self, payment: Payment) -> None:
        if payment.version == 0:
            self._session.add(PaymentTable(id=payment.id.value, version=1, **self._values(payment)))
        else:
            # Optimistic lock: the UPDATE only matches if nobody saved a newer version.
            result = self._session.exec(
                update(PaymentTable)
                .where(PaymentTable.id == payment.id.value, PaymentTable.version == payment.version)
                .values(
                    **self._values(payment),
                    version=payment.version + 1,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            if result.rowcount != 1:
                self._session.rollback()
                raise ConcurrentModificationException(payment.id.value)
        self._session.commit()
        payment.version += 1

    @staticmethod
    def _values(payment: Payment) -> dict[str, Any]:
        return {
            "cart_id": payment.cart_id.value,
            "customer_id": payment.customer_id.value,
            "amount": payment.amount.amount,
            "currency": payment.amount.currency,
            "status": payment.status.value,
            "method": payment.method.value if payment.method else None,
            "masked_card_number": payment.masked_card.value if payment.masked_card else None,
            "card_brand": payment.card_brand,
            "authorization_id": payment.authorization_id.value if payment.authorization_id else None,
            "gateway_transaction_id": (
                payment.gateway_transaction_id.value if payment.gateway_transaction_id else None
            ),
            "rejection_reason": payment.rejection_reason,
        }
