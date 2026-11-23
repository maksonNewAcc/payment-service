# tests/integration/test_postgres_payment_repo.py
# Runs the real repository against in-memory SQLite to check mapping and optimistic locking.
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.application.exceptions import ConcurrentModificationException
from app.domain.aggregates import Payment, PaymentStatus
from app.domain.value_objects import CardNumber, CartId, CustomerId, GatewayTransactionId, Money, PaymentMethod
from app.infrastructure import models  # noqa: F401
from app.infrastructure.postgres_payment_repo import PostgresPaymentRepository


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def new_payment() -> Payment:
    return Payment.create(CartId.new(), CustomerId.new(), Money(Decimal("249.98"), "PLN"))


def test_save_and_load_round_trips_all_state_without_full_card_number(engine):
    payment = new_payment()
    payment.provide_credit_card_details(CardNumber("4111111111111111"))
    payment.validate_credit_card(GatewayTransactionId("auth-1"))
    payment.select_payment_method(PaymentMethod.CARD)
    payment.mark_processed_successfully(GatewayTransactionId("cap-1"))

    with Session(engine) as session:
        PostgresPaymentRepository(session).save(payment)
    with Session(engine) as session:
        loaded = PostgresPaymentRepository(session).get_by_id(payment.id)
        raw_row = session.get(models.PaymentTable, payment.id.value)

    assert loaded is not None
    assert loaded.status is PaymentStatus.SUCCEEDED
    assert loaded.amount == Money(Decimal("249.98"), "PLN")
    assert loaded.method is PaymentMethod.CARD
    assert loaded.masked_card is not None and loaded.masked_card.value == "**** 1111"
    assert loaded.authorization_id == GatewayTransactionId("auth-1")
    assert loaded.gateway_transaction_id == GatewayTransactionId("cap-1")
    assert loaded.version == 1
    assert "4111111111111111" not in repr(raw_row.model_dump())


def test_save_increments_version_on_each_update(engine):
    payment = new_payment()
    with Session(engine) as session:
        repo = PostgresPaymentRepository(session)
        repo.save(payment)
        payment.select_payment_method(PaymentMethod.BLIK)
        repo.save(payment)

        assert payment.version == 2
        assert repo.get_by_id(payment.id).version == 2  # type: ignore[union-attr]


def test_concurrent_save_of_stale_copy_throws_and_keeps_first_write(engine):
    payment = new_payment()
    payment.select_payment_method(PaymentMethod.BLIK)
    with Session(engine) as session:
        PostgresPaymentRepository(session).save(payment)

    with Session(engine) as session_a, Session(engine) as session_b:
        repo_a, repo_b = PostgresPaymentRepository(session_a), PostgresPaymentRepository(session_b)
        copy_a, copy_b = repo_a.get_by_id(payment.id), repo_b.get_by_id(payment.id)
        assert copy_a is not None and copy_b is not None

        copy_a.mark_processed_successfully(GatewayTransactionId("blik-1"))
        repo_a.save(copy_a)

        copy_b.mark_rejected("declined")
        with pytest.raises(ConcurrentModificationException):
            repo_b.save(copy_b)

    with Session(engine) as session:
        stored = PostgresPaymentRepository(session).get_by_id(payment.id)
    assert stored is not None and stored.status is PaymentStatus.SUCCEEDED
