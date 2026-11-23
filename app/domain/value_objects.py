"""Value Objects and strongly typed identifiers.

Spec: docs/architecture/aggregates-and-invariants.md, sections 2 and 3. Validation lives in
__post_init__ so it runs on every construction path (HTTP, dataclasses.replace, repository load).
"""

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from enum import Enum
from typing import Self, final
from uuid import UUID, uuid4
from app.domain.exceptions import (
    CurrencyMismatchException,
    InvalidBlikCodeException,
    InvalidCardNumberException,
    InvalidCurrencyException,
    InvalidGatewayTransactionIdException,
    InvalidMoneyException,
)

_CENT = Decimal("0.01")


# --- Strongly typed identifiers ---------------------------------------------


@final
@dataclass(frozen=True, slots=True)
class PaymentId:
    value: UUID

    @classmethod
    def new(cls) -> Self:
        return cls(uuid4())


@final
@dataclass(frozen=True, slots=True)
class CartId:
    value: UUID

    @classmethod
    def new(cls) -> Self:
        return cls(uuid4())


@final
@dataclass(frozen=True, slots=True)
class CustomerId:
    value: UUID

    @classmethod
    def new(cls) -> Self:
        return cls(uuid4())


@final
@dataclass(frozen=True, slots=True)
class GatewayTransactionId:
    """Authorization reference returned by Card Network / Bank Issuer System or BLIK Payment."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip() or len(self.value) > 64:
            raise InvalidGatewayTransactionIdException(self.value)


# --- Enumerations -----------------------------------------------------------


class PaymentMethod(str, Enum):
    """Select payment method / Available Payment Options."""

    CARD = "CARD"
    BLIK = "BLIK"


# --- Value Objects ----------------------------------------------------------


@final
@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise InvalidMoneyException(self.amount)
        if self.amount < 0:
            raise InvalidMoneyException(self.amount)
        if (
            not isinstance(self.currency, str)
            or len(self.currency) != 3
            or not (self.currency.isascii() and self.currency.isalpha())
        ):
            raise InvalidCurrencyException(self.currency)
        object.__setattr__(self, "currency", self.currency.upper())
        object.__setattr__(self, "amount", self.amount.quantize(_CENT, rounding=ROUND_HALF_EVEN))

    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise CurrencyMismatchException(self.currency, other.currency)
        return Money(self.amount + other.amount, self.currency)


@final
@dataclass(frozen=True, slots=True)
class MaskedCardNumber:
    """The only form of a card number allowed in Payment Summary, storage and logs."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not re.fullmatch(r"\*\*\*\* \d{4}", self.value):
            raise InvalidCardNumberException("masked form must look like '**** 1234'")

    @property
    def last4(self) -> str:
        return self.value[-4:]


@final
@dataclass(frozen=True, slots=True)
class CardNumber:
    """Full card number. Lives only in memory, to call the Card Network / Bank Issuer System."""

    digits: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.digits, str):
            raise InvalidCardNumberException("must be a string")
        cleaned = re.sub(r"[\s-]", "", self.digits)
        if not cleaned.isascii() or not cleaned.isdigit():
            raise InvalidCardNumberException("must contain only digits, spaces or dashes")
        if not (13 <= len(cleaned) <= 19):
            raise InvalidCardNumberException("must have 13 to 19 digits")
        if not _passes_luhn(cleaned):
            raise InvalidCardNumberException("failed the Luhn checksum")
        object.__setattr__(self, "digits", cleaned)

    def __repr__(self) -> str:
        return f"CardNumber({self.masked().value!r})"

    __str__ = __repr__

    def masked(self) -> MaskedCardNumber:
        return MaskedCardNumber(f"**** {self.digits[-4:]}")

    @property
    def brand(self) -> str:
        """Issuer from the IIN/BIN prefix and length (Card Format rules)."""
        d, n = self.digits, len(self.digits)
        if d.startswith(("34", "37")) and n == 15:
            return "American Express"
        if n == 16 and (51 <= int(d[:2]) <= 55 or 2221 <= int(d[:4]) <= 2720):
            return "MasterCard"
        if d.startswith("4") and n in (13, 16, 19):
            return "Visa"
        if 16 <= n <= 19 and 3528 <= int(d[:4]) <= 3589:
            return "JCB"
        return "Unknown"


@final
@dataclass(frozen=True, slots=True)
class BlikCode:
    """One-time 6-digit code the customer reads from their banking app (BLIK Payment)."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not re.fullmatch(r"\d{6}", self.value):
            raise InvalidBlikCodeException()


def _passes_luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0
