from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.financial import (
    Payment, Settlement, Refund, Dispute,
    ReconciliationResult, ReconciliationException,
)
from app.schemas.financial import DashboardSummary
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    payments = await db.execute(
        select(
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.amount), 0),
            func.coalesce(func.sum(Payment.fee), 0),
            func.coalesce(func.sum(Payment.tax), 0),
        ).where(Payment.status == "captured")
    )
    p_count, gross_revenue, total_fees, total_tax = payments.one()

    settlements = await db.execute(
        select(
            func.count(Settlement.id),
            func.coalesce(func.sum(Settlement.amount), 0),
        ).where(Settlement.status == "settled")
    )
    s_count, settled_amount = settlements.one()

    pending_settlements = await db.execute(
        select(func.coalesce(func.sum(Settlement.amount), 0)).where(
            Settlement.status.in_(["created", "processed"])
        )
    )
    pending_amount = pending_settlements.scalar() or 0

    refunds_total = await db.execute(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(Refund.status == "processed")
    )
    total_refunds = refunds_total.scalar() or 0

    disputes_total = await db.execute(
        select(func.coalesce(func.sum(Dispute.amount), 0))
    )
    total_chargebacks = disputes_total.scalar() or 0

    matched = await db.execute(
        select(func.count(ReconciliationResult.id)).where(
            ReconciliationResult.status == "matched"
        )
    )
    matched_count = matched.scalar() or 0

    total_recon = await db.execute(select(func.count(ReconciliationResult.id)))
    total_recon_count = total_recon.scalar() or 0
    unmatched_count = total_recon_count - matched_count

    recon_pct = (matched_count / total_recon_count * 100) if total_recon_count > 0 else 0.0

    critical = await db.execute(
        select(func.count(ReconciliationException.id)).where(
            ReconciliationException.severity == "critical",
            ReconciliationException.status == "open",
        )
    )
    critical_count = critical.scalar() or 0

    net_revenue = float(gross_revenue) - float(total_fees) - float(total_tax) - float(total_refunds)

    return DashboardSummary(
        gross_revenue=float(gross_revenue),
        net_revenue=net_revenue,
        settled_amount=float(settled_amount),
        pending_amount=float(pending_amount),
        total_refunds=float(total_refunds),
        total_chargebacks=float(total_chargebacks),
        reconciliation_percentage=round(recon_pct, 2),
        matched_records=matched_count,
        unmatched_records=unmatched_count,
        critical_exceptions=critical_count,
        total_payments=p_count,
        total_settlements=s_count,
    )
