from decimal import Decimal
from uuid import UUID
from app.application.dtos import PaymentOptionsDto, PaymentSummaryDto
from app.application.gateways import BlikPaymentGateway, CardNetwork
from app.application.repositories import PaymentRepository
from app.domain.aggregates import Payment, PaymentStatus
from app.domain.exceptions import (
    BlikCodeRequiredException,
    CardAuthorizationDeclinedException,
    PaymentNotFoundException,
)
from app.domain.value_objects import (
    BlikCode,
    CardNumber,
    CartId,
    CustomerId,
    Money,
    PaymentId,
    PaymentMethod,
)


class PaymentApplicationService:
    def __init__(
        self,
        repository: PaymentRepository,
        card_network: CardNetwork,
        blik_gateway: BlikPaymentGateway,
    ) -> None:
        self._repository = repository
        self._card_network = card_network
        self._blik_gateway = blik_gateway

    def start_payment(
        self, cart_id: UUID, customer_id: UUID, amount: Decimal, currency: str
    ) -> PaymentSummaryDto:
        """Reaction to Checkout initiated (Shopping Cart context)."""
        payment = Payment.create(CartId(cart_id), CustomerId(customer_id), Money(amount, currency))
        self._repository.save(payment)
        return self._to_dto(payment)

    def get_payment_summary(self, payment_id: UUID) -> PaymentSummaryDto:
        return self._to_dto(self._get_existing_payment(payment_id))

    def get_available_payment_options(self, payment_id: UUID) -> PaymentOptionsDto:
        payment = self._get_existing_payment(payment_id)
        methods: tuple[PaymentMethod, ...] = ()
        if payment.status is PaymentStatus.PENDING:
            methods = (PaymentMethod.BLIK,)
        elif payment.status is PaymentStatus.CARD_VALIDATED:
            methods = (PaymentMethod.CARD, PaymentMethod.BLIK)
        return PaymentOptionsDto(payment.id.value, tuple(m.value for m in methods))

    def provide_credit_card_details(self, payment_id: UUID, card_number: str) -> PaymentSummaryDto:
        """Provide credit card details, then the Payment Service validates the card right away.

        The full CardNumber exists only inside this call; only the masked form and the
        authorization reference are stored.
        """
        payment = self._get_existing_payment(payment_id)
        card = CardNumber(card_number)  # Card Format & Luhn Check Rules
        payment.provide_credit_card_details(card)

        result = self._card_network.authorize(payment.id, card, payment.amount)
        if not result.approved or result.transaction_id is None:
            raise CardAuthorizationDeclinedException(payment.id.value, result.decline_reason or "declined")

        payment.validate_credit_card(result.transaction_id)
        self._repository.save(payment)
        return self._to_dto(payment)

    def select_payment_method(self, payment_id: UUID, method: str) -> PaymentSummaryDto:
        payment = self._get_existing_payment(payment_id)
        payment.select_payment_method(PaymentMethod(method))
        self._repository.save(payment)
        return self._to_dto(payment)

    def process_payment(self, payment_id: UUID, blik_code: str | None = None) -> PaymentSummaryDto:
        payment = self._get_existing_payment(payment_id)
        payment.ensure_can_be_processed()  # never call a gateway for a finished payment

        if payment.method is PaymentMethod.CARD:
            assert payment.authorization_id is not None
            result = self._card_network.capture(payment.id, payment.authorization_id, payment.amount)
        else:
            if blik_code is None:
                raise BlikCodeRequiredException(payment.id.value)
            result = self._blik_gateway.charge(payment.id, BlikCode(blik_code), payment.amount)

        if result.approved and result.transaction_id is not None:
            payment.mark_processed_successfully(result.transaction_id)
        else:
            payment.mark_rejected(result.decline_reason or "declined")
        self._repository.save(payment)
        return self._to_dto(payment)

    def _get_existing_payment(self, payment_id: UUID) -> Payment:
        payment = self._repository.get_by_id(PaymentId(payment_id))
        if payment is None:
            raise PaymentNotFoundException(payment_id)
        return payment

    @staticmethod
    def _to_dto(payment: Payment) -> PaymentSummaryDto:
        return PaymentSummaryDto(
            payment_id=payment.id.value,
            cart_id=payment.cart_id.value,
            customer_id=payment.customer_id.value,
            amount=payment.amount.amount,
            currency=payment.amount.currency,
            status=payment.status.value,
            method=payment.method.value if payment.method else None,
            masked_card_number=payment.masked_card.value if payment.masked_card else None,
            card_brand=payment.card_brand,
            gateway_transaction_id=(
                payment.gateway_transaction_id.value if payment.gateway_transaction_id else None
            ),
            rejection_reason=payment.rejection_reason,
        )
