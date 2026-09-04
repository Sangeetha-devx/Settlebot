import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.database import get_db
from app.models.user import User
from app.models.financial import ReconciliationResult, ReconciliationException
from app.services.auth import get_current_user
from app.services.adapters.razorpay_adapter import RazorpayAdapter
from app.services.adapters.bank_csv_adapter import BankCSVAdapter
from app.services.normalization import normalize
from app.services.reconciliation import reconcile, MatchStatus
from app.services.csv_export import export_bank_csv

router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"])


@router.post("/run")
async def run_reconciliation(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    rz_adapter = RazorpayAdapter(db)
    rz_raw = await rz_adapter.fetch()

    bank_csv = await export_bank_csv(db)
    bank_adapter = BankCSVAdapter(bank_csv)
    bank_raw = await bank_adapter.fetch()

    rz_norm = normalize(rz_raw)
    bank_norm = normalize(bank_raw)

    report = reconcile(rz_norm.records, bank_norm.records)

    await _persist_results(db, report)

    return {
        "status": "success",
        "run_id": report.run_id,
        "match_rate": report.match_rate,
        "summary": report.summary,
    }


@router.get("/results")
async def get_results(
    run_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    query = select(ReconciliationResult)
    if run_id:
        query = query.where(ReconciliationResult.run_id == run_id)
    if status:
        query = query.where(ReconciliationResult.status == status)
    query = query.order_by(ReconciliationResult.id.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.scalars().all()

    count_query = select(func.count(ReconciliationResult.id))
    if run_id:
        count_query = count_query.where(ReconciliationResult.run_id == run_id)
    if status:
        count_query = count_query.where(ReconciliationResult.status == status)
    total = (await db.execute(count_query)).scalar()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "results": [
            {
                "id": r.id,
                "run_id": r.run_id,
                "settlement_id": r.settlement_id,
                "payment_id": r.payment_id,
                "bank_reference": r.bank_reference,
                "status": r.status,
                "confidence": r.confidence,
                "expected_amount": r.expected_amount,
                "actual_amount": r.actual_amount,
                "difference": r.difference,
                "matched_by": r.matched_by,
                "evidence": r.evidence,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/runs")
async def list_runs(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(
            ReconciliationResult.run_id,
            func.count(ReconciliationResult.id).label("total"),
            func.min(ReconciliationResult.created_at).label("started_at"),
        )
        .group_by(ReconciliationResult.run_id)
        .order_by(func.min(ReconciliationResult.created_at).desc())
    )
    runs = []
    for row in result.all():
        matched = await db.execute(
            select(func.count(ReconciliationResult.id)).where(
                ReconciliationResult.run_id == row[0],
                ReconciliationResult.status.in_(["matched", "timing_difference"]),
            )
        )
        matched_count = matched.scalar() or 0
        rate = round(matched_count / max(row[1], 1) * 100, 2)
        runs.append({
            "run_id": row[0],
            "total_records": row[1],
            "matched": matched_count,
            "match_rate": rate,
            "started_at": row[2].isoformat() if row[2] else None,
        })
    return {"runs": runs}


@router.get("/summary/{run_id}")
async def run_summary(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    total = await db.execute(
        select(func.count(ReconciliationResult.id)).where(ReconciliationResult.run_id == run_id)
    )
    total_count = total.scalar() or 0
    if total_count == 0:
        return {"error": "Run not found"}

    statuses = await db.execute(
        select(ReconciliationResult.status, func.count(ReconciliationResult.id))
        .where(ReconciliationResult.run_id == run_id)
        .group_by(ReconciliationResult.status)
    )
    by_status = {row[0]: row[1] for row in statuses.all()}

    methods = await db.execute(
        select(ReconciliationResult.matched_by, func.count(ReconciliationResult.id))
        .where(ReconciliationResult.run_id == run_id)
        .group_by(ReconciliationResult.matched_by)
    )
    by_method = {row[0]: row[1] for row in methods.all()}

    amounts = await db.execute(
        select(
            func.coalesce(func.sum(ReconciliationResult.expected_amount), 0),
            func.coalesce(func.sum(ReconciliationResult.actual_amount), 0),
            func.coalesce(func.sum(func.abs(ReconciliationResult.difference)), 0),
        ).where(ReconciliationResult.run_id == run_id)
    )
    expected, actual, diff = amounts.one()

    matched_count = by_status.get("matched", 0) + by_status.get("timing_difference", 0)
    match_rate = round(matched_count / max(total_count, 1) * 100, 2)

    return {
        "run_id": run_id,
        "total_records": total_count,
        "match_rate": match_rate,
        "by_status": by_status,
        "by_method": by_method,
        "total_expected": float(expected),
        "total_actual": float(actual),
        "total_difference": float(diff),
    }


async def _persist_results(db: AsyncSession, report) -> None:
    await db.execute(
        text("DELETE FROM reconciliation_exceptions WHERE run_id = :rid"),
        {"rid": report.run_id},
    )
    await db.execute(
        text("DELETE FROM reconciliation_results WHERE run_id = :rid"),
        {"rid": report.run_id},
    )

    for r in report.results:
        db.add(ReconciliationResult(
            run_id=r.run_id,
            settlement_id=r.settlement_id,
            payment_id=r.payment_id,
            bank_reference=r.bank_reference,
            status=r.status,
            confidence=r.confidence,
            expected_amount=r.expected_amount,
            actual_amount=r.actual_amount,
            difference=r.difference,
            matched_by=r.matched_by,
            evidence=r.evidence,
        ))

    await db.commit()
