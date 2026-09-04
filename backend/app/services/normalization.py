"""
Normalization engine: converts raw data from all adapters into a unified,
clean canonical form suitable for the reconciliation engine.

Handles: date normalization, currency standardization, ID cleaning,
amount rounding, status mapping, duplicate detection, missing field defaults.
"""

from datetime import datetime, timezone
from dataclasses import dataclass, field
from app.services.adapters.base import CanonicalTransaction, TransactionType


RAZORPAY_STATUS_MAP = {
    "captured": "completed",
    "authorized": "pending",
    "created": "pending",
    "refunded": "refunded",
    "failed": "failed",
    "processed": "completed",
    "settled": "completed",
    "open": "open",
    "under_review": "pending",
    "won": "resolved",
    "lost": "resolved",
}

BANK_TYPE_MAP = {
    "credit": "completed",
    "debit": "completed",
    "cr": "completed",
    "dr": "completed",
}


@dataclass
class NormalizedTransaction:
    source: str
    source_id: str
    transaction_type: str
    amount: float
    currency: str
    date: datetime
    status: str
    reference_id: str | None = None
    parent_id: str | None = None
    settlement_id: str | None = None
    method: str | None = None
    fee: float = 0.0
    tax: float = 0.0
    net_amount: float = 0.0
    description: str | None = None
    utr: str | None = None
    metadata: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


@dataclass
class NormalizationResult:
    records: list[NormalizedTransaction]
    total_input: int
    total_output: int
    duplicates_removed: int
    warnings: list[str]
    stats: dict

    @property
    def by_source(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.records:
            counts[r.source] = counts.get(r.source, 0) + 1
        return counts

    @property
    def by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.records:
            counts[r.transaction_type] = counts.get(r.transaction_type, 0) + 1
        return counts


def normalize(records: list[CanonicalTransaction]) -> NormalizationResult:
    total_input = len(records)
    warnings: list[str] = []
    normalized: list[NormalizedTransaction] = []

    for raw in records:
        norm = _normalize_single(raw)
        normalized.append(norm)
        warnings.extend(
            f"[{raw.source_id}] {w}" for w in norm.warnings
        )

    before_dedup = len(normalized)
    normalized, dup_count, dup_warnings = _deduplicate(normalized)
    warnings.extend(dup_warnings)

    stats = _compute_stats(normalized)

    return NormalizationResult(
        records=normalized,
        total_input=total_input,
        total_output=len(normalized),
        duplicates_removed=dup_count,
        warnings=warnings,
        stats=stats,
    )


def _normalize_single(raw: CanonicalTransaction) -> NormalizedTransaction:
    warnings: list[str] = []

    amount = _normalize_amount(raw.amount)
    if amount < 0:
        warnings.append("Negative amount converted to absolute value")
        amount = abs(amount)

    fee = _normalize_amount(raw.fee)
    tax = _normalize_amount(raw.tax)

    if raw.transaction_type in (TransactionType.PAYMENT.value, TransactionType.SETTLEMENT.value):
        net_amount = round(amount - fee - tax, 2)
    else:
        net_amount = amount

    date = _normalize_date(raw.date)
    if date is None:
        date = datetime.now(timezone.utc)
        warnings.append("Missing date, defaulted to current time")

    status = _normalize_status(raw.status, raw.source)
    if status == "unknown":
        warnings.append(f"Unmapped status '{raw.status}', set to 'unknown'")

    source_id = _clean_id(raw.source_id)
    if not source_id:
        source_id = f"missing_{id(raw)}"
        warnings.append("Missing source_id, generated placeholder")

    currency = (raw.currency or "INR").upper().strip()
    if currency != "INR":
        warnings.append(f"Non-INR currency detected: {currency}")

    method = raw.method.lower().strip() if raw.method else None

    utr = raw.utr.strip() if raw.utr else None

    reference_id = _clean_id(raw.reference_id) if raw.reference_id else None
    parent_id = _clean_id(raw.parent_id) if raw.parent_id else None
    settlement_id = _clean_id(raw.settlement_id) if raw.settlement_id else None

    return NormalizedTransaction(
        source=raw.source,
        source_id=source_id,
        transaction_type=raw.transaction_type,
        amount=amount,
        currency=currency,
        date=date,
        status=status,
        reference_id=reference_id,
        parent_id=parent_id,
        settlement_id=settlement_id,
        method=method,
        fee=fee,
        tax=tax,
        net_amount=net_amount,
        description=raw.description,
        utr=utr,
        metadata=raw.metadata or {},
        warnings=warnings,
    )


def _normalize_amount(value: float | None) -> float:
    if value is None:
        return 0.0
    return round(float(value), 2)


def _normalize_date(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_status(raw_status: str | None, source: str) -> str:
    if not raw_status or str(raw_status).strip().lower() == "none":
        if source == "bank":
            return "completed"
        return "unknown"

    status_lower = raw_status.strip().lower()

    if source == "razorpay":
        return RAZORPAY_STATUS_MAP.get(status_lower, "unknown")
    elif source == "bank":
        return BANK_TYPE_MAP.get(status_lower, "completed")
    elif source == "internal":
        return RAZORPAY_STATUS_MAP.get(status_lower, status_lower)

    return status_lower


def _clean_id(raw_id: str | None) -> str:
    if not raw_id:
        return ""
    return raw_id.strip()


def _deduplicate(
    records: list[NormalizedTransaction],
) -> tuple[list[NormalizedTransaction], int, list[str]]:
    seen: dict[str, NormalizedTransaction] = {}
    unique: list[NormalizedTransaction] = []
    dup_count = 0
    warnings: list[str] = []

    for r in records:
        key = _dedup_key(r)
        if key in seen:
            dup_count += 1
            existing = seen[key]
            warnings.append(
                f"Duplicate removed: {r.source_id} matches {existing.source_id} "
                f"(source={r.source}, type={r.transaction_type}, amount={r.amount})"
            )
        else:
            seen[key] = r
            unique.append(r)

    return unique, dup_count, warnings


def _dedup_key(r: NormalizedTransaction) -> str:
    return f"{r.source}:{r.source_id}"


def _compute_stats(records: list[NormalizedTransaction]) -> dict:
    total_amount = sum(r.amount for r in records)
    total_fees = sum(r.fee for r in records)
    total_tax = sum(r.tax for r in records)

    sources: dict[str, float] = {}
    types: dict[str, float] = {}
    methods: dict[str, int] = {}
    statuses: dict[str, int] = {}

    for r in records:
        sources[r.source] = sources.get(r.source, 0) + r.amount
        types[r.transaction_type] = types.get(r.transaction_type, 0) + r.amount
        if r.method:
            methods[r.method] = methods.get(r.method, 0) + 1
        statuses[r.status] = statuses.get(r.status, 0) + 1

    with_warnings = sum(1 for r in records if r.warnings)

    return {
        "total_amount": round(total_amount, 2),
        "total_fees": round(total_fees, 2),
        "total_tax": round(total_tax, 2),
        "amount_by_source": {k: round(v, 2) for k, v in sources.items()},
        "amount_by_type": {k: round(v, 2) for k, v in types.items()},
        "method_distribution": methods,
        "status_distribution": statuses,
        "records_with_warnings": with_warnings,
    }
