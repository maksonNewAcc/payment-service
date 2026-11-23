# tests/unit/domain/test_value_objects.py
# Spec: docs/architecture/aggregates-and-invariants.md, sections 2 and 3.
import dataclasses
import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.exceptions import (
    CurrencyMismatchException,
    InvalidBlikCodeException,
    InvalidCardNumberException,
    InvalidCurrencyException,
    InvalidGatewayTransactionIdException,
    InvalidMoneyException,
)
from app.domain.value_objects import (
    BlikCode,
    CardNumber,
    CartId,
    CustomerId,
    GatewayTransactionId,
    MaskedCardNumber,
    Money,
    PaymentId,
)

CARDS = json.loads((Path(__file__).parent / "test_cards.json").read_text())


# --- CardNumber --------------------------------------------------------------

@pytest.mark.parametrize("card_number", [c["number"] for c in CARDS])
def test_card_number_when_valid_card_is_created(card_number: str):
    assert CardNumber(card_number).digits == card_number.replace(" ", "").replace("-", "")


@pytest.mark.parametrize(("card_number", "expected_brand"), [(c["number"], c["type"]) for c in CARDS])
def test_card_number_brand_matches_issuer(card_number: str, expected_brand: str):
    assert CardNumber(card_number).brand == expected_brand


def test_card_number_strips_spaces_and_dashes():
    assert CardNumber("4111 1111-1111 1111").digits == "4111111111111111"


@pytest.mark.parametrize(
    "invalid_number",
    ["4111 1111 1111 1112", "4111a11111111111", "411111111111", "41111111111111111111", "", "４１１１１１１１１１１１１１１１"],
)
def test_card_number_when_invalid_throws_invalid_card_number_exception(invalid_number: str):
    with pytest.raises(InvalidCardNumberException) as exc_info:
        CardNumber(invalid_number)

    assert exc_info.value.code == "payment.invalid_card_number"
    assert invalid_number.replace(" ", "") not in str(exc_info.value) or invalid_number == ""


def test_card_number_masked_returns_last_four_digits():
    assert CardNumber("4111111111111111").masked() == MaskedCardNumber("**** 1111")


def test_card_number_repr_and_str_never_show_full_number():
    card = CardNumber("4111111111111111")

    assert "4111111111111111" not in repr(card)
    assert "4111111111111111" not in str(card)
    assert "**** 1111" in repr(card)


@pytest.mark.parametrize("invalid_mask", ["4111", "**** 11a1", "1111 1111", "****1111"])
def test_masked_card_number_when_wrong_format_throws(invalid_mask: str):
    with pytest.raises(InvalidCardNumberException):
        MaskedCardNumber(invalid_mask)


# --- BlikCode / GatewayTransactionId -----------------------------------------

def test_blik_code_when_six_digits_is_valid():
    assert BlikCode("123456").value == "123456"


@pytest.mark.parametrize("invalid_code", ["12345", "1234567", "12a456", "", 123456])
def test_blik_code_when_not_six_digits_throws(invalid_code: object):
    with pytest.raises(InvalidBlikCodeException):
        BlikCode(invalid_code)  # type: ignore[arg-type]


def test_blik_code_repr_hides_code():
    assert "123456" not in repr(BlikCode("123456"))


@pytest.mark.parametrize("invalid_value", ["", "   ", "x" * 65, None])
def test_gateway_transaction_id_when_blank_or_too_long_throws(invalid_value: object):
    with pytest.raises(InvalidGatewayTransactionIdException):
        GatewayTransactionId(invalid_value)  # type: ignore[arg-type]


# --- Money -------------------------------------------------------------------

@pytest.mark.parametrize("invalid_amount", [19.99, 10, True, "19.99", Decimal("-0.01"), Decimal("NaN")])
def test_money_when_amount_invalid_throws_invalid_money_exception(invalid_amount: object):
    with pytest.raises(InvalidMoneyException):
        Money(invalid_amount, "PLN")  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_currency", ["zl", "PLN1", "", 985])
def test_money_when_currency_invalid_throws_invalid_currency_exception(invalid_currency: object):
    with pytest.raises(InvalidCurrencyException):
        Money(Decimal("1.00"), invalid_currency)  # type: ignore[arg-type]


def test_money_normalises_currency_and_rounds_half_even():
    assert Money(Decimal("0.125"), "pln") == Money(Decimal("0.12"), "PLN")


def test_money_add_when_currencies_differ_throws_currency_mismatch_exception():
    with pytest.raises(CurrencyMismatchException):
        Money(Decimal("1.00"), "PLN").add(Money(Decimal("1.00"), "EUR"))


# --- Immutability and strongly typed identifiers -----------------------------

@pytest.mark.parametrize(
    "value_object",
    [
        Money(Decimal("1.00"), "PLN"),
        CardNumber("4111111111111111"),
        MaskedCardNumber("**** 1111"),
        BlikCode("123456"),
        GatewayTransactionId("tx-1"),
        PaymentId.new(),
        CartId.new(),
        CustomerId.new(),
    ],
)
def test_value_objects_are_frozen_and_slotted(value_object: object):
    assert not hasattr(value_object, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(value_object, dataclasses.fields(value_object)[0].name, None)


def test_ids_of_different_types_are_never_equal_for_same_uuid():
    raw = uuid4()

    assert PaymentId(raw) != CartId(raw)
    assert PaymentId(raw) == PaymentId(raw)
    assert PaymentId.new() != PaymentId.new()
