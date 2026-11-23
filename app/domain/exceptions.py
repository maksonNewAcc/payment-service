from abc import ABC
from decimal import Decimal
from typing import final
from uuid import UUID


class DomainException(Exception, ABC):
    def __init__(self, code: str, message: str) -> None:
        if type(self) is DomainException:
            raise TypeError("DomainException is abstract and cannot be instantiated directly.")
        self.code = code
        super().__init__(message)


# --- Value objects ---------------------------------------------------------


@final
class InvalidMoneyException(DomainException):
    def __init__(self, attempted_amount: object) -> None:
        self.attempted_amount = attempted_amount
        super().__init__(
            code="money.invalid_amount",
            message=f"Money amount must be a finite, non-negative Decimal, but was {attempted_amount!r}.",
        )


@final
class InvalidCurrencyException(DomainException):
    def __init__(self, attempted_currency: object) -> None:
        self.attempted_currency = attempted_currency
        super().__init__(
            code="money.invalid_currency",
            message=f"Currency must be a 3-letter ISO 4217 code, but was {attempted_currency!r}.",
        )


@final
class CurrencyMismatchException(DomainException):
    def __init__(self, expected_currency: str, actual_currency: str) -> None:
        self.expected_currency = expected_currency
        self.actual_currency = actual_currency
        super().__init__(
            code="money.currency_mismatch",
            message=f"Cannot combine {expected_currency} with {actual_currency}.",
        )


@final
class InvalidCardNumberException(DomainException):
    def __init__(self, reason: str) -> None:
        # Never include the card number itself: it must not reach logs or responses.
        self.reason = reason
        super().__init__(code="payment.invalid_card_number", message=f"Invalid card number: {reason}.")


@final
class InvalidBlikCodeException(DomainException):
    def __init__(self) -> None:
        super().__init__(code="payment.invalid_blik_code", message="BLIK code must be exactly 6 digits.")


@final
class InvalidGatewayTransactionIdException(DomainException):
    def __init__(self, attempted_value: object) -> None:
        self.attempted_value = attempted_value
        super().__init__(
            code="payment.invalid_gateway_transaction_id",
            message=f"Gateway transaction id must be a non-blank string of max 64 chars, but was {attempted_value!r}.",
        )


# --- Payment aggregate -----------------------------------------------------


@final
class InvalidPaymentAmountException(DomainException):
    def __init__(self, attempted_amount: Decimal, currency: str) -> None:
        self.attempted_amount = attempted_amount
        self.currency = currency
        super().__init__(
            code="payment.invalid_amount",
            message=f"Payment amount must be greater than zero, but was {attempted_amount} {currency}.",
        )


@final
class IllegalPaymentStateTransitionException(DomainException):
    def __init__(self, payment_id: UUID, status: str, action: str) -> None:
        self.payment_id = payment_id
        self.status = status
        self.action = action
        super().__init__(
            code="payment.illegal_state_transition",
            message=f"Cannot {action} for Payment {payment_id} in status {status}.",
        )


@final
class PaymentAlreadyFinalizedException(DomainException):
    def __init__(self, payment_id: UUID, status: str) -> None:
        self.payment_id = payment_id
        self.status = status
        super().__init__(
            code="payment.already_finalized",
            message=f"Payment {payment_id} is already {status} and cannot be processed again.",
        )


@final
class BlikCodeRequiredException(DomainException):
    def __init__(self, payment_id: UUID) -> None:
        self.payment_id = payment_id
        super().__init__(
            code="payment.blik_code_required",
            message=f"Payment {payment_id} uses BLIK; a BLIK code is required to process it.",
        )


@final
class CardAuthorizationDeclinedException(DomainException):
    def __init__(self, payment_id: UUID, reason: str) -> None:
        self.payment_id = payment_id
        self.reason = reason
        super().__init__(
            code="payment.card_declined",
            message=f"Card for Payment {payment_id} was declined by the card network: {reason}.",
        )


@final
class PaymentNotFoundException(DomainException):
    def __init__(self, payment_id: UUID) -> None:
        self.payment_id = payment_id
        super().__init__(code="payment.not_found", message=f"Payment {payment_id} was not found.")
