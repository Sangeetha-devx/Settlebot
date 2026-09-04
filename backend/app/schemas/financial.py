from pydantic import BaseModel
from datetime import datetime


class PaymentResponse(BaseModel):
    id: int
    payment_id: str
    order_id: str | None
    amount: float
    currency: str
    status: str
    method: str | None
    fee: float
    tax: float
    settlement_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SettlementResponse(BaseModel):
    id: int
    settlement_id: str
    amount: float
    status: str
    fees: float
    tax: float
    utr: str | None
    created_at: datetime
    settled_at: datetime | None

    model_config = {"from_attributes": True}


class RefundResponse(BaseModel):
    id: int
    refund_id: str
    payment_id: str
    amount: float
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DisputeResponse(BaseModel):
    id: int
    dispute_id: str
    payment_id: str
    amount: float
    status: str
    reason_code: str | None
    phase: str | None
    respond_by: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BankTransactionResponse(BaseModel):
    id: int
    reference: str | None
    amount: float
    type: str
    date: datetime
    description: str | None
    balance: float | None
    utr: str | None

    model_config = {"from_attributes": True}


class DashboardSummary(BaseModel):
    gross_revenue: float
    net_revenue: float
    settled_amount: float
    pending_amount: float
    total_refunds: float
    total_chargebacks: float
    reconciliation_percentage: float
    matched_records: int
    unmatched_records: int
    critical_exceptions: int
    total_payments: int
    total_settlements: int


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
