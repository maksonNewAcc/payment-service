from dataclasses import asdict
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response, status
from sqlmodel import Session
from app.application.payment_service import PaymentApplicationService
from app.infrastructure.database import get_session
from app.infrastructure.postgres_payment_repo import PostgresPaymentRepository
from app.infrastructure.simulated_gateways import SimulatedBlikGateway, SimulatedCardNetwork
from app.presentation.contracts import (
    ProcessPaymentRequest,
    ProvideCardDetailsRequest,
    SelectPaymentMethodRequest,
    StartPaymentRequest,
)

router = APIRouter(prefix="/api/payments", tags=["Payment"])


def get_payment_service(session: Session = Depends(get_session)) -> PaymentApplicationService:
    return PaymentApplicationService(
        PostgresPaymentRepository(session), SimulatedCardNetwork(), SimulatedBlikGateway()
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def start_payment(
    payload: StartPaymentRequest,
    request: Request,
    response: Response,
    service: PaymentApplicationService = Depends(get_payment_service),
):
    dto = service.start_payment(payload.cart_id, payload.customer_id, payload.amount, payload.currency)
    response.headers["Location"] = str(request.url_for("get_payment", payment_id=dto.payment_id))
    return asdict(dto)


@router.get("/{payment_id}", name="get_payment")
def get_payment(
    payment_id: UUID,
    service: PaymentApplicationService = Depends(get_payment_service),
):
    return asdict(service.get_payment_summary(payment_id))


@router.get("/{payment_id}/options")
def get_available_payment_options(
    payment_id: UUID,
    service: PaymentApplicationService = Depends(get_payment_service),
):
    return asdict(service.get_available_payment_options(payment_id))


@router.post("/{payment_id}/card")
def provide_credit_card_details(
    payment_id: UUID,
    payload: ProvideCardDetailsRequest,
    service: PaymentApplicationService = Depends(get_payment_service),
):
    return asdict(service.provide_credit_card_details(payment_id, payload.card_number))


@router.post("/{payment_id}/method")
def select_payment_method(
    payment_id: UUID,
    payload: SelectPaymentMethodRequest,
    service: PaymentApplicationService = Depends(get_payment_service),
):
    return asdict(service.select_payment_method(payment_id, payload.method))


@router.post("/{payment_id}/process")
def process_payment(
    payment_id: UUID,
    payload: ProcessPaymentRequest,
    service: PaymentApplicationService = Depends(get_payment_service),
):
    return asdict(service.process_payment(payment_id, payload.blik_code))
