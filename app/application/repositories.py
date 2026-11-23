from typing import Protocol
from app.domain.aggregates import Payment
from app.domain.value_objects import PaymentId


class PaymentRepository(Protocol):
    def get_by_id(self, payment_id: PaymentId) -> Payment | None: ...

    def save(self, payment: Payment) -> None:
        """Persist the payment. Raises ConcurrentModificationException when the stored
        version differs from payment.version (someone else saved it in the meantime)."""
        ...
