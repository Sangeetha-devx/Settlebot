from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TransactionType(str, Enum):
    PAYMENT = "payment"
    SETTLEMENT = "settlement"
    REFUND = "refund"
    DISPUTE = "dispute"
    FEE = "fee"
    BANK_CREDIT = "bank_credit"
    BANK_DEBIT = "bank_debit"


class DataSource(str, Enum):
    RAZORPAY = "razorpay"
    BANK = "bank"
    INTERNAL = "internal"


@dataclass
class CanonicalTransaction:
    """Unified transaction model all adapters normalize into."""
    source: str
    source_id: str
    transaction_type: str
    amount: float
    currency: str = "INR"
    date: datetime | None = None
    status: str | None = None
    reference_id: str | None = None
    parent_id: str | None = None
    settlement_id: str | None = None
    method: str | None = None
    fee: float = 0.0
    tax: float = 0.0
    description: str | None = None
    utr: str | None = None
    metadata: dict = field(default_factory=dict)


class BaseAdapter(ABC):
    """Interface every data source adapter must implement."""

    source: DataSource

    @abstractmethod
    async def fetch(self, **kwargs) -> list[CanonicalTransaction]:
        ...

    @abstractmethod
    async def validate(self, raw_data: any) -> list[str]:
        """Return a list of validation error messages (empty = valid)."""
        ...
