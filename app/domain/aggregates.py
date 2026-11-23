from dataclasses import dataclass, field
from enum import Enum
from app.domain.events import (
    CreditCardDetailsProvided,
    CreditCardValidated,
    DomainEvent,
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
    MaskedCardNumber,
    Money,
    PaymentId,
    PaymentMethod,
)


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    CARD_VALIDATED = "CARD_VALIDATED"
    METHOD_SELECTED = "METHOD_SELECTED"
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"


_FINAL_STATUSES = (PaymentStatus.SUCCEEDED, PaymentStatus.REJECTED)


@dataclass
class Payment:
    """Payment swimlane of the board: Provide credit card details -> Validate credit card ->
    Select payment method -> Process payment.

    CARD must go through card details and validation before it can be selected.
    BLIK skips the card steps, so a BLIK customer is never forced to enter a card.
    """

    id: PaymentId
    cart_id: CartId
    customer_id: CustomerId
    amount: Money
    _status: PaymentStatus = field(default=PaymentStatus.PENDING, repr=False)
    _method: PaymentMethod | None = field(default=None, repr=False)
    _masked_card: MaskedCardNumber | None = field(default=None, repr=False)
    _card_brand: str | None = field(default=None, repr=False)
    _authorization_id: GatewayTransactionId | None = field(default=None, repr=False)
    _gateway_transaction_id: GatewayTransactionId | None = field(default=None, repr=False)
    _rejection_reason: str | None = field(default=None, repr=False)
    version: int = field(default=0, repr=False)
    _domain_events: list[DomainEvent] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if self.amount.amount <= 0:
            raise InvalidPaymentAmountException(self.amount.amount, self.amount.currency)

    @classmethod
    def create(cls, cart_id: CartId, customer_id: CustomerId, amount: Money) -> "Payment":
        return cls(id=PaymentId.new(), cart_id=cart_id, customer_id=customer_id, amount=amount)

    # --- Queries ---------------------------------------------------------

    @property
    def status(self) -> PaymentStatus:
        return self._status

    @property
    def method(self) -> PaymentMethod | None:
        return self._method

    @property
    def masked_card(self) -> MaskedCardNumber | None:
        return self._masked_card

    @property
    def card_brand(self) -> str | None:
        return self._card_brand

    @property
    def authorization_id(self) -> GatewayTransactionId | None:
        return self._authorization_id

    @property
    def gateway_transaction_id(self) -> GatewayTransactionId | None:
        return self._gateway_transaction_id

    @property
    def rejection_reason(self) -> str | None:
        return self._rejection_reason

    @property
    def is_finalized(self) -> bool:
        return self._status in _FINAL_STATUSES

    @property
    def domain_events(self) -> tuple[DomainEvent, ...]:
        return tuple(self._domain_events)

    # --- Commands --------------------------------------------------------

    def provide_credit_card_details(self, card: CardNumber) -> None:
        """Customer: Provide credit card details. Only the masked number is kept."""
        self._ensure_status("provide credit card details", PaymentStatus.PENDING)
        self._masked_card = card.masked()
        self._card_brand = card.brand
        self._domain_events.append(
            CreditCardDetailsProvided(
                payment_id=self.id.value,
                masked_card_number=self._masked_card.value,
                card_brand=self._card_brand,
            )
        )

    def validate_credit_card(self, authorization_id: GatewayTransactionId) -> None:
        """Payment Service: Validate credit card, after the Card Network authorized the card."""
        self._ensure_status("validate credit card", PaymentStatus.PENDING)
        if self._masked_card is None:
            raise IllegalPaymentStateTransitionException(
                self.id.value, self._status.value, "validate credit card before card details are provided"
            )
        self._authorization_id = authorization_id
        self._status = PaymentStatus.CARD_VALIDATED
        self._domain_events.append(
            CreditCardValidated(payment_id=self.id.value, authorization_id=authorization_id.value)
        )

    def select_payment_method(self, method: PaymentMethod) -> None:
        """Customer: Select payment method."""
        if method is PaymentMethod.CARD:
            self._ensure_status("select CARD without a validated card", PaymentStatus.CARD_VALIDATED)
        else:
            self._ensure_status("select BLIK", PaymentStatus.PENDING, PaymentStatus.CARD_VALIDATED)
        self._method = method
        self._status = PaymentStatus.METHOD_SELECTED
        self._domain_events.append(PaymentMethodSelected(payment_id=self.id.value, method=method.value))

    def ensure_can_be_processed(self) -> None:
        """Guard checked BEFORE calling a gateway, so a finished payment is never charged twice."""
        self._ensure_status("process payment", PaymentStatus.METHOD_SELECTED)

    def mark_processed_successfully(self, transaction_id: GatewayTransactionId) -> None:
        """Payment Service: Process payment -> Payment processed successfully."""
        self.ensure_can_be_processed()
        assert self._method is not None
        self._gateway_transaction_id = transaction_id
        self._status = PaymentStatus.SUCCEEDED
        self._domain_events.append(
            PaymentProcessedSuccessfully(
                payment_id=self.id.value,
                cart_id=self.cart_id.value,
                customer_id=self.customer_id.value,
                amount=self.amount.amount,
                currency=self.amount.currency,
                method=self._method.value,
                gateway_transaction_id=transaction_id.value,
            )
        )

    def mark_rejected(self, reason: str) -> None:
        """Payment Service: Process payment -> Payment rejected."""
        self.ensure_can_be_processed()
        assert self._method is not None
        self._rejection_reason = reason
        self._status = PaymentStatus.REJECTED
        self._domain_events.append(
            PaymentRejected(
                payment_id=self.id.value,
                cart_id=self.cart_id.value,
                customer_id=self.customer_id.value,
                method=self._method.value,
                reason=reason,
            )
        )

    # --- Invariants ------------------------------------------------------

    def _ensure_status(self, action: str, *allowed: PaymentStatus) -> None:
        if self.is_finalized:
            raise PaymentAlreadyFinalizedException(self.id.value, self._status.value)
        if self._status not in allowed:
            raise IllegalPaymentStateTransitionException(self.id.value, self._status.value, action)
