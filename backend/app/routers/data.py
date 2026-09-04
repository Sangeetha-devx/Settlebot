from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.financial import Payment, Settlement, Refund, Dispute, BankTransaction
from app.services.auth import get_current_user
from app.services.seed import seed_database
from app.services.synthetic_data import ErrorConfig

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("/generate")
async def generate_data(
    num_payments: int = Query(default=500, ge=50, le=5000),
    seed: int = Query(default=42),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    result = await seed_database(db, num_payments=num_payments, seed=seed)
    return {"status": "success", "message": "Synthetic data generated", **result}


@router.get("/stats")
async def data_stats(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    payments = await db.execute(select(func.count(Payment.id)))
    captured = await db.execute(
        select(func.count(Payment.id)).where(Payment.status == "captured")
    )
    failed = await db.execute(
        select(func.count(Payment.id)).where(Payment.status == "failed")
    )
    settlements = await db.execute(select(func.count(Settlement.id)))
    refunds = await db.execute(select(func.count(Refund.id)))
    disputes = await db.execute(select(func.count(Dispute.id)))
    bank_txns = await db.execute(select(func.count(BankTransaction.id)))

    payment_sum = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "captured")
    )
    settlement_sum = await db.execute(
        select(func.coalesce(func.sum(Settlement.amount), 0))
    )
    refund_sum = await db.execute(
        select(func.coalesce(func.sum(Refund.amount), 0))
    )
    dispute_sum = await db.execute(
        select(func.coalesce(func.sum(Dispute.amount), 0))
    )

    methods = await db.execute(
        select(Payment.method, func.count(Payment.id))
        .where(Payment.status == "captured")
        .group_by(Payment.method)
    )

    return {
        "counts": {
            "payments": payments.scalar(),
            "captured_payments": captured.scalar(),
            "failed_payments": failed.scalar(),
            "settlements": settlements.scalar(),
            "refunds": refunds.scalar(),
            "disputes": disputes.scalar(),
            "bank_transactions": bank_txns.scalar(),
        },
        "totals": {
            "payment_volume": float(payment_sum.scalar()),
            "settlement_volume": float(settlement_sum.scalar()),
            "refund_volume": float(refund_sum.scalar()),
            "dispute_volume": float(dispute_sum.scalar()),
        },
        "payment_methods": {row[0]: row[1] for row in methods.all()},
    }


@router.delete("/clear")
async def clear_data(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    from app.services.seed import clear_financial_data
    await clear_financial_data(db)
    return {"status": "success", "message": "All financial data cleared"}
