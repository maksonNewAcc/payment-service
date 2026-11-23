from uuid import UUID


class ConcurrentModificationException(Exception):
    """Optimistic-lock conflict: the payment was changed by another request."""

    def __init__(self, payment_id: UUID) -> None:
        self.payment_id = payment_id
        self.code = "payment.concurrent_modification"
        super().__init__(f"Payment {payment_id} was modified by another request; reload and retry.")
