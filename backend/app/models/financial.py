from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.sql import func
from app.database import Base
import enum


class PaymentStatus(str, enum.Enum):
    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    REFUNDED = "refunded"
    FAILED = "failed"


class PaymentMethod(str, enum.Enum):
    UPI = "upi"
    CARD = "card"
    NETBANKING = "netbanking"
    WALLET = "wallet"
    EMI = "emi"


class SettlementStatus(str, enum.Enum):
    CREATED = "created"
    PROCESSED = "processed"
    SETTLED = "settled"
    FAILED = "failed"


class ReconciliationStatus(str, enum.Enum):
    MATCHED = "matched"
    PARTIALLY_MATCHED = "partially_matched"
    UNMATCHED = "unmatched"
    TIMING_DIFFERENCE = "timing_difference"
    AMOUNT_MISMATCH = "amount_mismatch"
    DUPLICATE = "duplicate"
    MISSING = "missing"
    REQUIRES_REVIEW = "requires_review"


class ExceptionSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExceptionType(str, enum.Enum):
    MISSING_TRANSACTION = "missing_transaction"
    DUPLICATE_TRANSACTION = "duplicate_transaction"
    AMOUNT_MISMATCH = "amount_mismatch"
    TIMING_DIFFERENCE = "timing_difference"
    UNEXPECTED_FEE = "unexpected_fee"
    UNEXPECTED_REFUND = "unexpected_refund"
    UNEXPECTED_CHARGEBACK = "unexpected_chargeback"
    MISSING_SETTLEMENT = "missing_settlement"
    BANK_ONLY_RECORD = "bank_only_record"
    RAZORPAY_ONLY_RECORD = "razorpay_only_record"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(String(50), unique=True, nullable=False, index=True)
    order_id = Column(String(50), index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="INR")
    status = Column(String(20), nullable=False)
    method = Column(String(20))
    description = Column(String(255))
    fee = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    settlement_id = Column(String(50), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    captured_at = Column(DateTime(timezone=True))


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True, index=True)
    settlement_id = Column(String(50), unique=True, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)
    fees = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    utr = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    settled_at = Column(DateTime(timezone=True))


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    refund_id = Column(String(50), unique=True, nullable=False, index=True)
    payment_id = Column(String(50), ForeignKey("payments.payment_id"), index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, index=True)
    dispute_id = Column(String(50), unique=True, nullable=False, index=True)
    payment_id = Column(String(50), ForeignKey("payments.payment_id"), index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)
    reason_code = Column(String(50))
    phase = Column(String(30))
    respond_by = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String(100), index=True)
    amount = Column(Float, nullable=False)
    type = Column(String(10), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    description = Column(String(255))
    balance = Column(Float)
    utr = Column(String(50), index=True)


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(50), index=True, nullable=False)
    settlement_id = Column(String(50), index=True)
    payment_id = Column(String(50), index=True)
    bank_reference = Column(String(100))
    status = Column(String(30), nullable=False)
    confidence = Column(Float, default=0.0)
    expected_amount = Column(Float)
    actual_amount = Column(Float)
    difference = Column(Float, default=0.0)
    evidence = Column(Text)
    matched_by = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReconciliationException(Base):
    __tablename__ = "reconciliation_exceptions"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(50), index=True, nullable=False)
    reconciliation_id = Column(Integer, ForeignKey("reconciliation_results.id"), nullable=True)
    type = Column(String(40), nullable=False)
    severity = Column(String(10), nullable=False)
    description = Column(Text)
    root_cause = Column(Text)
    evidence = Column(Text)
    confidence = Column(Float, default=0.0)
    recommended_action = Column(Text)
    status = Column(String(20), default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    intent = Column(Text)
    tools_called = Column(Text)
    data_retrieved = Column(Text)
    calculations = Column(Text)
    recommendation = Column(Text)
    confidence = Column(Float)
    approval = Column(String(20))
    details = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
