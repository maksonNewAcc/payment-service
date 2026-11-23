# tests/unit/application/test_payment_service.py
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.application.gateways import GatewayResult
from app.application.payment_service import PaymentApplicationService
from app.domain.aggregates import Payment, PaymentStatus
from app.domain.exceptions import (
    BlikCodeRequiredException,
    CardAuthorizationDeclinedException,
    InvalidCardNumberException,
    PaymentAlreadyFinalizedException,
    PaymentNotFoundException,
)
from app.domain.value_objects import (
    CardNumber,
    CartId,
    CustomerId,
    GatewayTransactionId,
    Money,
    PaymentMethod,
)


def make_sut(payment: Payment | None = None):
    repo, card_network, blik = MagicMock(), MagicMock(), MagicMock()
    repo.get_by_id.return_value = payment
    return PaymentApplicationService(repo, card_network, blik), repo, card_network, blik


def new_payment() -> Payment:
    return Payment.create(CartId.new(), CustomerId.new(), Money(Decimal("249.98"), "PLN"))


def approved(tx: str) -> GatewayResult:
    return GatewayResult(True, GatewayTransactionId(tx))


def test_start_payment_creates_pending_payment_and_saves():
    sut, repo, *_ = make_sut()
    cart_id = uuid4()

    result = sut.start_payment(cart_id, uuid4(), Decimal("249.98"), "PLN")

    assert result.cart_id == cart_id
    assert result.status == "PENDING"
    assert result.amount == Decimal("249.98")
    repo.save.assert_called_once()


def test_provide_card_details_authorizes_with_network_and_saves_masked_card():
    payment = new_payment()
    sut, repo, card_network, _ = make_sut(payment)
    card_network.authorize.return_value = approved("auth-1")

    result = sut.provide_credit_card_details(payment.id.value, "4111 1111 1111 1111")

    card = card_network.authorize.call_args.args[1]
    assert card_network.authorize.call_args.args[0] == payment.id  # idempotency key
    assert card.digits == "4111111111111111"
    assert result.status == "CARD_VALIDATED"
    assert result.masked_card_number == "**** 1111"
    assert "4111111111111111" not in repr(result)
    repo.save.assert_called_once_with(payment)


def test_provide_card_details_when_luhn_fails_never_calls_network_or_saves():
    payment = new_payment()
    sut, repo, card_network, _ = make_sut(payment)

    with pytest.raises(InvalidCardNumberException):
        sut.provide_credit_card_details(payment.id.value, "4111 1111 1111 1112")

    card_network.authorize.assert_not_called()
    repo.save.assert_not_called()


def test_provide_card_details_when_network_declines_throws_and_never_saves():
    payment = new_payment()
    sut, repo, card_network, _ = make_sut(payment)
    card_network.authorize.return_value = GatewayResult(False, decline_reason="stolen card")

    with pytest.raises(CardAuthorizationDeclinedException) as exc_info:
        sut.provide_credit_card_details(payment.id.value, "4111111111111111")

    assert exc_info.value.reason == "stolen card"
    repo.save.assert_not_called()


def test_get_options_when_card_not_validated_offers_only_blik():
    payment = new_payment()
    sut, *_ = make_sut(payment)

    assert sut.get_available_payment_options(payment.id.value).available_methods == ("BLIK",)


def test_process_card_payment_captures_authorization_and_records_success():
    payment = new_payment()
    payment.provide_credit_card_details(CardNumber("4111111111111111"))
    payment.validate_credit_card(GatewayTransactionId("auth-1"))
    payment.select_payment_method(PaymentMethod.CARD)
    sut, repo, card_network, blik = make_sut(payment)
    card_network.capture.return_value = approved("cap-1")

    result = sut.process_payment(payment.id.value)

    card_network.capture.assert_called_once_with(payment.id, GatewayTransactionId("auth-1"), payment.amount)
    blik.charge.assert_not_called()
    assert result.status == "SUCCEEDED"
    assert result.gateway_transaction_id == "cap-1"
    repo.save.assert_called_once_with(payment)


def test_process_blik_payment_when_bank_rejects_records_rejection_and_saves():
    payment = new_payment()
    payment.select_payment_method(PaymentMethod.BLIK)
    sut, repo, _, blik = make_sut(payment)
    blik.charge.return_value = GatewayResult(False, decline_reason="BLIK code rejected by the bank")

    result = sut.process_payment(payment.id.value, blik_code="000000")

    assert result.status == "REJECTED"
    assert result.rejection_reason == "BLIK code rejected by the bank"
    repo.save.assert_called_once_with(payment)


def test_process_blik_payment_without_code_throws_and_never_charges():
    payment = new_payment()
    payment.select_payment_method(PaymentMethod.BLIK)
    sut, repo, _, blik = make_sut(payment)

    with pytest.raises(BlikCodeRequiredException):
        sut.process_payment(payment.id.value)

    blik.charge.assert_not_called()
    repo.save.assert_not_called()


def test_process_when_already_finalized_never_calls_gateway():
    payment = new_payment()
    payment.select_payment_method(PaymentMethod.BLIK)
    payment.mark_processed_successfully(GatewayTransactionId("blik-1"))
    sut, repo, card_network, blik = make_sut(payment)

    with pytest.raises(PaymentAlreadyFinalizedException):
        sut.process_payment(payment.id.value, blik_code="123456")

    blik.charge.assert_not_called()
    card_network.capture.assert_not_called()
    repo.save.assert_not_called()
    assert payment.status is PaymentStatus.SUCCEEDED


def test_get_payment_when_missing_throws_not_found():
    sut, *_ = make_sut(None)
    missing = uuid4()

    with pytest.raises(PaymentNotFoundException) as exc_info:
        sut.get_payment_summary(missing)

    assert exc_info.value.payment_id == missing
