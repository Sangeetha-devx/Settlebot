import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field

PAYMENT_METHODS = ["upi", "card", "netbanking", "wallet", "emi"]
PAYMENT_METHOD_WEIGHTS = [0.45, 0.25, 0.15, 0.10, 0.05]
DISPUTE_REASONS = [
    "chargeback", "fraud", "product_not_received",
    "duplicate", "quality_issue", "not_as_described",
]
DISPUTE_PHASES = ["chargeback", "pre_arbitration", "arbitration"]

FEE_RATE = 0.02
GST_RATE = 0.18
SETTLEMENT_CYCLE_DAYS = 2


def _rand_id(prefix: str, length: int = 14) -> str:
    chars = string.ascii_letters + string.digits
    return f"{prefix}_{''.join(random.choices(chars, k=length))}"


def _rand_amount(low: int = 100, high: int = 50000) -> float:
    return round(random.uniform(low, high), 2)


def _rand_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    offset = random.random() * delta.total_seconds()
    return start + timedelta(seconds=offset)


@dataclass
class ErrorConfig:
    missing_payment_rate: float = 0.03
    missing_settlement_rate: float = 0.02
    duplicate_payment_rate: float = 0.02
    amount_mismatch_rate: float = 0.03
    timing_difference_days: int = 3
    timing_difference_rate: float = 0.04
    unexpected_fee_rate: float = 0.02
    bank_only_record_count: int = 5


@dataclass
class GeneratedData:
    payments: list = field(default_factory=list)
    settlements: list = field(default_factory=list)
    refunds: list = field(default_factory=list)
    disputes: list = field(default_factory=list)
    bank_transactions: list = field(default_factory=list)
    injected_errors: list = field(default_factory=list)

    @property
    def total_records(self) -> int:
        return (
            len(self.payments) + len(self.settlements) + len(self.refunds)
            + len(self.disputes) + len(self.bank_transactions)
        )


def generate_synthetic_data(
    num_payments: int = 500,
    seed: int | None = 42,
    error_config: ErrorConfig | None = None,
) -> GeneratedData:
    if seed is not None:
        random.seed(seed)

    if error_config is None:
        error_config = ErrorConfig()

    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=60)

    data = GeneratedData()

    # --- 1. Generate payments ---
    payment_ids = []
    for i in range(num_payments):
        payment_id = _rand_id("pay")
        order_id = _rand_id("order")
        amount = _rand_amount()
        method = random.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS, k=1)[0]
        created_at = _rand_date(start_date, now - timedelta(days=SETTLEMENT_CYCLE_DAYS))

        is_failed = random.random() < 0.08
        status = "failed" if is_failed else "captured"

        fee = round(amount * FEE_RATE, 2) if status == "captured" else 0.0
        tax = round(fee * GST_RATE, 2) if status == "captured" else 0.0

        payment = {
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "status": status,
            "method": method,
            "description": f"Order {order_id}",
            "fee": fee,
            "tax": tax,
            "settlement_id": None,
            "created_at": created_at,
            "captured_at": created_at + timedelta(seconds=random.randint(1, 30)) if status == "captured" else None,
        }
        data.payments.append(payment)
        if status == "captured":
            payment_ids.append(i)

    # --- 2. Group captured payments into settlements ---
    captured_indices = list(payment_ids)
    random.shuffle(captured_indices)

    settlement_groups = []
    pos = 0
    while pos < len(captured_indices):
        batch_size = random.randint(8, 30)
        group = captured_indices[pos : pos + batch_size]
        settlement_groups.append(group)
        pos += batch_size

    for group in settlement_groups:
        settlement_id = _rand_id("setl")
        utr = f"UTR{random.randint(100000000000, 999999999999)}"

        gross = sum(data.payments[i]["amount"] for i in group)
        total_fees = sum(data.payments[i]["fee"] for i in group)
        total_tax = sum(data.payments[i]["tax"] for i in group)
        net_amount = round(gross - total_fees - total_tax, 2)

        earliest_payment = min(data.payments[i]["created_at"] for i in group)
        settled_at = earliest_payment + timedelta(days=SETTLEMENT_CYCLE_DAYS, hours=random.randint(0, 12))

        for i in group:
            data.payments[i]["settlement_id"] = settlement_id

        settlement = {
            "settlement_id": settlement_id,
            "amount": net_amount,
            "status": "settled",
            "fees": round(total_fees, 2),
            "tax": round(total_tax, 2),
            "utr": utr,
            "created_at": earliest_payment + timedelta(days=1),
            "settled_at": settled_at,
        }
        data.settlements.append(settlement)

    # --- 3. Generate refunds (5-8% of captured payments) ---
    refund_candidates = random.sample(
        captured_indices, k=int(len(captured_indices) * random.uniform(0.05, 0.08))
    )
    for idx in refund_candidates:
        payment = data.payments[idx]
        is_partial = random.random() < 0.3
        refund_amount = round(payment["amount"] * random.uniform(0.2, 0.8), 2) if is_partial else payment["amount"]

        refund = {
            "refund_id": _rand_id("rfnd"),
            "payment_id": payment["payment_id"],
            "amount": refund_amount,
            "status": "processed",
            "created_at": payment["created_at"] + timedelta(days=random.randint(1, 15)),
        }
        data.refunds.append(refund)

    # --- 4. Generate disputes (2-3% of captured payments) ---
    dispute_pool = [i for i in captured_indices if i not in refund_candidates]
    dispute_candidates = random.sample(
        dispute_pool, k=int(len(dispute_pool) * random.uniform(0.02, 0.03))
    )
    for idx in dispute_candidates:
        payment = data.payments[idx]
        created_at = payment["created_at"] + timedelta(days=random.randint(5, 30))

        dispute = {
            "dispute_id": _rand_id("disp"),
            "payment_id": payment["payment_id"],
            "amount": payment["amount"],
            "status": random.choice(["open", "under_review", "won", "lost"]),
            "reason_code": random.choice(DISPUTE_REASONS),
            "phase": random.choice(DISPUTE_PHASES),
            "respond_by": created_at + timedelta(days=3),
            "created_at": created_at,
        }
        data.disputes.append(dispute)

    # --- 5. Generate bank transactions matching settlements ---
    for settlement in data.settlements:
        bank_txn = {
            "reference": f"NEFT-{random.randint(10000000, 99999999)}",
            "amount": settlement["amount"],
            "type": "credit",
            "date": settlement["settled_at"],
            "description": f"RAZORPAY SETTLEMENT {settlement['settlement_id']}",
            "balance": round(random.uniform(50000, 500000), 2),
            "utr": settlement["utr"],
        }
        data.bank_transactions.append(bank_txn)

    # --- 6. Inject controlled errors ---
    _inject_errors(data, error_config)

    return data


def _inject_errors(data: GeneratedData, config: ErrorConfig) -> None:
    captured_payments = [p for p in data.payments if p["status"] == "captured"]

    # Missing payments: remove settlement_id from some payments (simulates gateway-only records)
    missing_count = int(len(captured_payments) * config.missing_payment_rate)
    missing_targets = random.sample(captured_payments, k=min(missing_count, len(captured_payments)))
    for p in missing_targets:
        data.injected_errors.append({
            "type": "missing_in_bank",
            "payment_id": p["payment_id"],
            "description": "Payment exists in Razorpay but has no matching bank record",
        })

    # Missing settlements: mark some settlements as not having bank records
    missing_setl_count = max(1, int(len(data.settlements) * config.missing_settlement_rate))
    missing_setl_targets = random.sample(data.settlements, k=min(missing_setl_count, len(data.settlements)))
    for s in missing_setl_targets:
        bank_match = [b for b in data.bank_transactions if b["utr"] == s["utr"]]
        if bank_match:
            data.bank_transactions.remove(bank_match[0])
            data.injected_errors.append({
                "type": "missing_settlement_in_bank",
                "settlement_id": s["settlement_id"],
                "description": "Settlement processed but no corresponding bank credit found",
            })

    # Duplicate payments
    dup_count = int(len(captured_payments) * config.duplicate_payment_rate)
    dup_targets = random.sample(captured_payments, k=min(dup_count, len(captured_payments)))
    for p in dup_targets:
        dup = p.copy()
        dup["payment_id"] = _rand_id("pay")
        dup["order_id"] = p["order_id"]
        data.payments.append(dup)
        data.injected_errors.append({
            "type": "duplicate_payment",
            "original_payment_id": p["payment_id"],
            "duplicate_payment_id": dup["payment_id"],
            "description": "Duplicate payment for the same order",
        })

    # Amount mismatches in bank records
    mismatch_count = max(1, int(len(data.bank_transactions) * config.amount_mismatch_rate))
    mismatch_targets = random.sample(
        data.bank_transactions, k=min(mismatch_count, len(data.bank_transactions))
    )
    for b in mismatch_targets:
        original = b["amount"]
        offset = round(random.uniform(-500, 500), 2)
        if offset == 0:
            offset = 100.0
        b["amount"] = round(original + offset, 2)
        data.injected_errors.append({
            "type": "amount_mismatch",
            "bank_reference": b["reference"],
            "expected": original,
            "actual": b["amount"],
            "difference": round(offset, 2),
            "description": "Bank amount does not match expected settlement amount",
        })

    # Timing differences: shift some bank transaction dates
    timing_count = max(1, int(len(data.bank_transactions) * config.timing_difference_rate))
    timing_targets = random.sample(
        data.bank_transactions, k=min(timing_count, len(data.bank_transactions))
    )
    for b in timing_targets:
        shift = timedelta(days=random.randint(1, config.timing_difference_days))
        b["date"] = b["date"] + shift
        data.injected_errors.append({
            "type": "timing_difference",
            "bank_reference": b["reference"],
            "shift_days": shift.days,
            "description": f"Bank transaction date shifted by {shift.days} day(s)",
        })

    # Unexpected fee adjustments
    fee_count = max(1, int(len(captured_payments) * config.unexpected_fee_rate))
    fee_targets = random.sample(captured_payments, k=min(fee_count, len(captured_payments)))
    for p in fee_targets:
        original_fee = p["fee"]
        p["fee"] = round(original_fee * random.uniform(1.5, 3.0), 2)
        data.injected_errors.append({
            "type": "unexpected_fee",
            "payment_id": p["payment_id"],
            "expected_fee": original_fee,
            "actual_fee": p["fee"],
            "description": "Fee charged is significantly higher than expected rate",
        })

    # Bank-only records (no matching Razorpay data)
    for _ in range(config.bank_only_record_count):
        bank_txn = {
            "reference": f"NEFT-{random.randint(10000000, 99999999)}",
            "amount": _rand_amount(500, 20000),
            "type": "credit",
            "date": _rand_date(
                datetime.now(timezone.utc) - timedelta(days=30),
                datetime.now(timezone.utc),
            ),
            "description": "UNKNOWN CREDIT",
            "balance": round(random.uniform(50000, 500000), 2),
            "utr": f"UTR{random.randint(100000000000, 999999999999)}",
        }
        data.bank_transactions.append(bank_txn)
        data.injected_errors.append({
            "type": "bank_only_record",
            "bank_reference": bank_txn["reference"],
            "amount": bank_txn["amount"],
            "description": "Credit in bank with no matching Razorpay settlement",
        })
