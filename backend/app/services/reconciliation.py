"""
Core reconciliation engine: matches settlements against payments, bank records,
refunds, and disputes using multiple strategies in priority order.

All financial calculations are deterministic — no LLM involvement.
"""

import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from app.services.normalization import NormalizedTransaction


TIMING_WINDOW_DAYS = 3
AMOUNT_TOLERANCE = 0.01
PARTIAL_MATCH_THRESHOLD = 0.95


class MatchStatus:
    MATCHED = "matched"
    PARTIALLY_MATCHED = "partially_matched"
    UNMATCHED = "unmatched"
    TIMING_DIFFERENCE = "timing_difference"
    AMOUNT_MISMATCH = "amount_mismatch"
    DUPLICATE = "duplicate"
    MISSING = "missing"
    REQUIRES_REVIEW = "requires_review"


class MatchMethod:
    EXACT_ID = "exact_id"
    UTR_MATCH = "utr_match"
    EXACT_AMOUNT = "exact_amount"
    AMOUNT_DATE = "amount_date"
    AGGREGATE = "aggregate"
    FEE_ADJUSTED = "fee_adjusted"
    PARTIAL = "partial"


@dataclass
class MatchResult:
    run_id: str
    settlement_id: str | None
    payment_id: str | None
    bank_reference: str | None
    status: str
    confidence: float
    expected_amount: float
    actual_amount: float
    difference: float
    matched_by: str
    evidence: str
    details: dict = field(default_factory=dict)


@dataclass
class ReconciliationReport:
    run_id: str
    started_at: datetime
    completed_at: datetime
    results: list[MatchResult]
    summary: dict

    @property
    def match_rate(self) -> float:
        if not self.results:
            return 0.0
        matched = sum(
            1 for r in self.results
            if r.status in (MatchStatus.MATCHED, MatchStatus.TIMING_DIFFERENCE)
        )
        return round(matched / len(self.results) * 100, 2)


def reconcile(
    razorpay_records: list[NormalizedTransaction],
    bank_records: list[NormalizedTransaction],
) -> ReconciliationReport:
    run_id = f"recon_{uuid.uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc)

    settlements = [r for r in razorpay_records if r.transaction_type == "settlement"]
    payments = [r for r in razorpay_records if r.transaction_type == "payment"]
    refunds = [r for r in razorpay_records if r.transaction_type == "refund"]
    disputes = [r for r in razorpay_records if r.transaction_type == "dispute"]
    bank_credits = [r for r in bank_records if r.transaction_type == "bank_credit"]

    payment_index = _build_index(payments, key="settlement_id")
    refund_index = _build_index(refunds, key="parent_id")
    dispute_index = _build_index(disputes, key="parent_id")

    results: list[MatchResult] = []
    matched_bank_ids: set[str] = set()
    matched_settlement_ids: set[str] = set()

    # Strategy 1: UTR matching (settlement UTR -> bank UTR)
    for settlement in settlements:
        if not settlement.utr:
            continue
        for bank in bank_credits:
            if bank.source_id in matched_bank_ids:
                continue
            if bank.utr and bank.utr == settlement.utr:
                result = _compare_settlement_to_bank(
                    run_id, settlement, bank, payments, refunds, disputes,
                    payment_index, refund_index, dispute_index,
                    MatchMethod.UTR_MATCH,
                )
                results.append(result)
                matched_bank_ids.add(bank.source_id)
                matched_settlement_ids.add(settlement.source_id)
                break

    # Strategy 2: Exact amount matching for unmatched settlements
    for settlement in settlements:
        if settlement.source_id in matched_settlement_ids:
            continue
        for bank in bank_credits:
            if bank.source_id in matched_bank_ids:
                continue
            if abs(settlement.amount - bank.amount) <= AMOUNT_TOLERANCE:
                result = _compare_settlement_to_bank(
                    run_id, settlement, bank, payments, refunds, disputes,
                    payment_index, refund_index, dispute_index,
                    MatchMethod.EXACT_AMOUNT,
                )
                results.append(result)
                matched_bank_ids.add(bank.source_id)
                matched_settlement_ids.add(settlement.source_id)
                break

    # Strategy 3: Amount + date window matching
    for settlement in settlements:
        if settlement.source_id in matched_settlement_ids:
            continue
        for bank in bank_credits:
            if bank.source_id in matched_bank_ids:
                continue
            amount_close = abs(settlement.amount - bank.amount) / max(settlement.amount, 1) < 0.05
            date_close = (
                settlement.date and bank.date
                and abs((settlement.date - bank.date).total_seconds()) < TIMING_WINDOW_DAYS * 86400
            )
            if amount_close and date_close:
                result = _compare_settlement_to_bank(
                    run_id, settlement, bank, payments, refunds, disputes,
                    payment_index, refund_index, dispute_index,
                    MatchMethod.AMOUNT_DATE,
                )
                results.append(result)
                matched_bank_ids.add(bank.source_id)
                matched_settlement_ids.add(settlement.source_id)
                break

    # Strategy 4: Aggregate matching — sum payments for settlement, compare to bank
    for settlement in settlements:
        if settlement.source_id in matched_settlement_ids:
            continue
        group_payments = payment_index.get(settlement.source_id, [])
        if not group_payments:
            continue
        gross = sum(p.amount for p in group_payments)
        fees = sum(p.fee for p in group_payments)
        tax = sum(p.tax for p in group_payments)

        group_refunds = []
        group_disputes = []
        for p in group_payments:
            group_refunds.extend(refund_index.get(p.source_id, []))
            group_disputes.extend(dispute_index.get(p.source_id, []))

        total_refunds = sum(r.amount for r in group_refunds)
        total_disputes = sum(d.amount for d in group_disputes)
        expected_net = round(gross - fees - tax - total_refunds - total_disputes, 2)

        for bank in bank_credits:
            if bank.source_id in matched_bank_ids:
                continue
            if abs(expected_net - bank.amount) / max(abs(expected_net), 1) < 0.05:
                diff = round(bank.amount - expected_net, 2)
                status = MatchStatus.MATCHED if abs(diff) <= AMOUNT_TOLERANCE else MatchStatus.AMOUNT_MISMATCH
                confidence = max(0.7, 1.0 - abs(diff) / max(abs(expected_net), 1))

                evidence = (
                    f"Aggregate match: {len(group_payments)} payments, "
                    f"gross={gross:.2f}, fees={fees:.2f}, tax={tax:.2f}, "
                    f"refunds={total_refunds:.2f}, disputes={total_disputes:.2f}, "
                    f"expected_net={expected_net:.2f}, bank={bank.amount:.2f}"
                )
                results.append(MatchResult(
                    run_id=run_id,
                    settlement_id=settlement.source_id,
                    payment_id=None,
                    bank_reference=bank.source_id,
                    status=status,
                    confidence=round(confidence, 4),
                    expected_amount=expected_net,
                    actual_amount=bank.amount,
                    difference=diff,
                    matched_by=MatchMethod.AGGREGATE,
                    evidence=evidence,
                    details={
                        "payment_count": len(group_payments),
                        "refund_count": len(group_refunds),
                        "dispute_count": len(group_disputes),
                    },
                ))
                matched_bank_ids.add(bank.source_id)
                matched_settlement_ids.add(settlement.source_id)
                break

    # Unmatched settlements (Razorpay-only)
    for settlement in settlements:
        if settlement.source_id in matched_settlement_ids:
            continue
        group_payments = payment_index.get(settlement.source_id, [])
        results.append(MatchResult(
            run_id=run_id,
            settlement_id=settlement.source_id,
            payment_id=None,
            bank_reference=None,
            status=MatchStatus.MISSING,
            confidence=1.0,
            expected_amount=settlement.amount,
            actual_amount=0.0,
            difference=-settlement.amount,
            matched_by="none",
            evidence=f"Settlement {settlement.source_id} has no matching bank record (UTR={settlement.utr})",
            details={"payment_count": len(group_payments)},
        ))

    # Unmatched bank records (bank-only)
    for bank in bank_credits:
        if bank.source_id in matched_bank_ids:
            continue
        results.append(MatchResult(
            run_id=run_id,
            settlement_id=None,
            payment_id=None,
            bank_reference=bank.source_id,
            status=MatchStatus.UNMATCHED,
            confidence=1.0,
            expected_amount=0.0,
            actual_amount=bank.amount,
            difference=bank.amount,
            matched_by="none",
            evidence=f"Bank credit {bank.source_id} ({bank.amount:.2f}) has no matching settlement (UTR={bank.utr})",
        ))

    # Duplicate detection across payments
    dup_results = _detect_duplicate_payments(run_id, payments)
    results.extend(dup_results)

    completed_at = datetime.now(timezone.utc)
    summary = _build_summary(results, started_at, completed_at)

    return ReconciliationReport(
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        results=results,
        summary=summary,
    )


def _build_index(
    records: list[NormalizedTransaction], key: str,
) -> dict[str, list[NormalizedTransaction]]:
    index: dict[str, list[NormalizedTransaction]] = {}
    for r in records:
        val = getattr(r, key, None)
        if val:
            index.setdefault(val, []).append(r)
    return index


def _compare_settlement_to_bank(
    run_id: str,
    settlement: NormalizedTransaction,
    bank: NormalizedTransaction,
    payments: list[NormalizedTransaction],
    refunds: list[NormalizedTransaction],
    disputes: list[NormalizedTransaction],
    payment_index: dict,
    refund_index: dict,
    dispute_index: dict,
    match_method: str,
) -> MatchResult:
    diff = round(bank.amount - settlement.amount, 2)
    abs_diff = abs(diff)

    if abs_diff <= AMOUNT_TOLERANCE:
        status = MatchStatus.MATCHED
        confidence = 1.0
    elif settlement.date and bank.date and abs((settlement.date - bank.date).days) > 1 and abs_diff <= AMOUNT_TOLERANCE:
        status = MatchStatus.TIMING_DIFFERENCE
        confidence = 0.95
    elif abs_diff / max(settlement.amount, 1) < 0.01:
        status = MatchStatus.MATCHED
        confidence = 0.98
    elif abs_diff / max(settlement.amount, 1) < 0.05:
        status = MatchStatus.AMOUNT_MISMATCH
        confidence = 0.85
    else:
        status = MatchStatus.AMOUNT_MISMATCH
        confidence = 0.6

    # Check for timing difference
    if settlement.date and bank.date:
        day_diff = abs((settlement.date - bank.date).days)
        if day_diff > 1 and status == MatchStatus.MATCHED:
            status = MatchStatus.TIMING_DIFFERENCE
            confidence = min(confidence, 0.95)

    group = payment_index.get(settlement.source_id, [])
    group_refunds = []
    group_disputes = []
    for p in group:
        group_refunds.extend(refund_index.get(p.source_id, []))
        group_disputes.extend(dispute_index.get(p.source_id, []))

    gross = sum(p.amount for p in group)
    fees = sum(p.fee for p in group)
    tax = sum(p.tax for p in group)
    total_refunds = sum(r.amount for r in group_refunds)
    total_disputes = sum(d.amount for d in group_disputes)

    evidence = (
        f"{match_method}: settlement={settlement.amount:.2f}, bank={bank.amount:.2f}, "
        f"diff={diff:.2f} | {len(group)} payments, gross={gross:.2f}, "
        f"fees={fees:.2f}, tax={tax:.2f}, "
        f"refunds={total_refunds:.2f}, disputes={total_disputes:.2f}"
    )

    return MatchResult(
        run_id=run_id,
        settlement_id=settlement.source_id,
        payment_id=None,
        bank_reference=bank.source_id,
        status=status,
        confidence=round(confidence, 4),
        expected_amount=settlement.amount,
        actual_amount=bank.amount,
        difference=diff,
        matched_by=match_method,
        evidence=evidence,
        details={
            "payment_count": len(group),
            "refund_count": len(group_refunds),
            "dispute_count": len(group_disputes),
            "gross": round(gross, 2),
            "fees": round(fees, 2),
            "tax": round(tax, 2),
            "total_refunds": round(total_refunds, 2),
            "total_disputes": round(total_disputes, 2),
        },
    )


def _detect_duplicate_payments(
    run_id: str, payments: list[NormalizedTransaction],
) -> list[MatchResult]:
    results = []
    seen: dict[str, NormalizedTransaction] = {}

    for p in payments:
        if not p.reference_id:
            continue
        key = f"{p.reference_id}:{p.amount}"
        if key in seen:
            original = seen[key]
            results.append(MatchResult(
                run_id=run_id,
                settlement_id=None,
                payment_id=p.source_id,
                bank_reference=None,
                status=MatchStatus.DUPLICATE,
                confidence=0.9,
                expected_amount=original.amount,
                actual_amount=p.amount,
                difference=0.0,
                matched_by="duplicate_detection",
                evidence=(
                    f"Duplicate: {p.source_id} and {original.source_id} share "
                    f"order={p.reference_id}, amount={p.amount:.2f}"
                ),
                details={
                    "original_payment_id": original.source_id,
                    "duplicate_payment_id": p.source_id,
                    "order_id": p.reference_id,
                },
            ))
        else:
            seen[key] = p

    return results


def _build_summary(
    results: list[MatchResult],
    started_at: datetime,
    completed_at: datetime,
) -> dict:
    total = len(results)
    by_status: dict[str, int] = {}
    by_method: dict[str, int] = {}
    total_expected = 0.0
    total_actual = 0.0
    total_diff = 0.0

    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_method[r.matched_by] = by_method.get(r.matched_by, 0) + 1
        total_expected += r.expected_amount
        total_actual += r.actual_amount
        total_diff += abs(r.difference)

    matched_count = by_status.get(MatchStatus.MATCHED, 0) + by_status.get(MatchStatus.TIMING_DIFFERENCE, 0)
    match_rate = round(matched_count / max(total, 1) * 100, 2)

    processing_ms = round((completed_at - started_at).total_seconds() * 1000, 1)

    return {
        "total_records": total,
        "matched": by_status.get(MatchStatus.MATCHED, 0),
        "partially_matched": by_status.get(MatchStatus.PARTIALLY_MATCHED, 0),
        "timing_differences": by_status.get(MatchStatus.TIMING_DIFFERENCE, 0),
        "amount_mismatches": by_status.get(MatchStatus.AMOUNT_MISMATCH, 0),
        "unmatched": by_status.get(MatchStatus.UNMATCHED, 0),
        "missing": by_status.get(MatchStatus.MISSING, 0),
        "duplicates": by_status.get(MatchStatus.DUPLICATE, 0),
        "requires_review": by_status.get(MatchStatus.REQUIRES_REVIEW, 0),
        "match_rate": match_rate,
        "by_status": by_status,
        "by_method": by_method,
        "total_expected": round(total_expected, 2),
        "total_actual": round(total_actual, 2),
        "total_difference": round(total_diff, 2),
        "processing_time_ms": processing_ms,
    }
