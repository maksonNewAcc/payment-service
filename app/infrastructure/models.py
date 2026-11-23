from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel


class AuditBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = None
    is_deleted: bool = Field(default=False)


class PaymentTable(AuditBase, table=True):
    """Stores only the masked card number; the full card number is never persisted."""

    __tablename__ = "payments"
    cart_id: UUID = Field(index=True)
    customer_id: UUID = Field(index=True)
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    currency: str = Field(max_length=3)
    status: str = Field(default="PENDING")
    method: Optional[str] = None
    masked_card_number: Optional[str] = Field(default=None, max_length=9)
    card_brand: Optional[str] = None
    authorization_id: Optional[str] = Field(default=None, max_length=64)
    gateway_transaction_id: Optional[str] = Field(default=None, max_length=64)
    rejection_reason: Optional[str] = None
    version: int = Field(default=0)
