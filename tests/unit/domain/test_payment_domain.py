# tests/unit/domain/test_payment_domain.py
from decimal import Decimal

import pytest

from app.domain.aggregates import Payment, PaymentStatus
from app.domain.events import (
    CreditCardDetailsProvided,
    CreditCardValidated,
    PaymentMethodSelected,
    PaymentProcessedSuccessfully,
    PaymentRejected,
)
from app.domain.exceptions import (
    IllegalPaymentStateTransitionException,
    InvalidPaymentAmountException,
    PaymentAlreadyFinalizedException,
)
from app.domain.value_objects import (
    CardNumber,
    CartId,
    CustomerId,
    GatewayTransactionId,
    Money,
    PaymentMethod,
)

VISA = CardNumber("4111111111111111")


def new_payment(amount: str = "249.98") -> Payment:
    return Payment.create(CartId.new(), CustomerId.new(), Money(Decimal(amount), "PLN"))


def card_payment_ready_to_process() -> Payment:
    payment = new_payment()
    payment.provide_credit_card_details(VISA)
    payment.validate_credit_card(GatewayTransactionId("auth-1"))
    payment.select_payment_method(PaymentMethod.CARD)
    return payment


def test_create_when_amount_is_zero_throws_invalid_payment_amount_exception():
    with pytest.raises(InvalidPaymentAmountException) as exc_info:
        new_payment("0.00")

    assert exc_info.value.code == "payment.invalid_amount"


def test_card_flow_follows_board_order_and_records_all_events():
    # Arrange
    payment = new_payment()

    # Act
    payment.provide_credit_card_details(VISA)
    payment.validate_credit_card(GatewayTransactionId("auth-1"))
    payment.select_payment_method(PaymentMethod.CARD)
    payment.mark_processed_successfully(GatewayTransactionId("cap-1"))

    # Assert
    assert payment.status is PaymentStatus.SUCCEEDED
    assert [type(e) for e in payment.domain_events] == [
        CreditCardDetailsProvided,
        CreditCardValidated,
        PaymentMethodSelected,
        PaymentProcessedSuccessfully,
    ]
    success = payment.domain_events[-1]
    assert isinstance(success, PaymentProcessedSuccessfully)
    assert success.amount == Decimal("249.98")
    assert success.cart_id == payment.cart_id.value
    assert success.gateway_transaction_id == "cap-1"


def test_provide_card_details_stores_only_masked_number():
    payment = new_payment()

    payment.provide_credit_card_details(VISA)

    assert payment.masked_card is not None and payment.masked_card.value == "**** 1111"
    assert payment.card_brand == "Visa"
    event = payment.domain_events[-1]
    assert isinstance(event, CreditCardDetailsProvided)
    assert "4111111111111111" not in repr(event)


def test_blik_flow_does_not_require_card_details():
    payment = new_payment()

    payment.select_payment_method(PaymentMethod.BLIK)
    payment.mark_processed_successfully(GatewayTransactionId("blik-1"))

    assert payment.status is PaymentStatus.SUCCEEDED
    assert payment.masked_card is None


def test_select_card_when_card_not_validated_throws_illegal_transition():
    payment = new_payment()
    payment.provide_credit_card_details(VISA)

    with pytest.raises(IllegalPaymentStateTransitionException) as exc_info:
        payment.select_payment_method(PaymentMethod.CARD)

    assert exc_info.value.code == "payment.illegal_state_transition"
    assert payment.status is PaymentStatus.PENDING


def test_validate_card_when_no_card_details_throws_illegal_transition():
    payment = new_payment()

    with pytest.raises(IllegalPaymentStateTransitionException):
        payment.validate_credit_card(GatewayTransactionId("auth-1"))


def test_provide_card_details_after_validation_throws_illegal_transition():
    payment = new_payment()
    payment.provide_credit_card_details(VISA)
    payment.validate_credit_card(GatewayTransactionId("auth-1"))

    with pytest.raises(IllegalPaymentStateTransitionException):
        payment.provide_credit_card_details(CardNumber("5555555555554444"))


def test_process_when_no_method_selected_throws_illegal_transition():
    payment = new_payment()

    with pytest.raises(IllegalPaymentStateTransitionException):
        payment.ensure_can_be_processed()


def test_rejection_records_payment_rejected_with_reason():
    payment = card_payment_ready_to_process()

    payment.mark_rejected("insufficient funds")

    assert payment.status is PaymentStatus.REJECTED
    event = payment.domain_events[-1]
    assert isinstance(event, PaymentRejected)
    assert event.reason == "insufficient funds"


@pytest.mark.parametrize("finish", ["success", "reject"])
def test_finalized_payment_cannot_be_processed_again(finish: str):
    # Invariant 7 (OrderFulfillment.md): a finished payment cannot be processed again.
    payment = card_payment_ready_to_process()
    if finish == "success":
        payment.mark_processed_successfully(GatewayTransactionId("cap-1"))
    else:
        payment.mark_rejected("declined")
    status_before = payment.status

    with pytest.raises(PaymentAlreadyFinalizedException) as exc_info:
        payment.mark_processed_successfully(GatewayTransactionId("cap-2"))

    assert exc_info.value.code == "payment.already_finalized"
    assert payment.status is status_before
    with pytest.raises(PaymentAlreadyFinalizedException):
        payment.select_payment_method(PaymentMethod.BLIK)
