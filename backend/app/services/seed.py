from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.models.financial import (
    Payment, Settlement, Refund, Dispute, BankTransaction,
)
from app.services.synthetic_data import generate_synthetic_data, ErrorConfig, GeneratedData


async def clear_financial_data(db: AsyncSession) -> None:
    for table in [
        "reconciliation_exceptions",
        "reconciliation_results",
        "bank_transactions",
        "disputes",
        "refunds",
        "payments",
        "settlements",
    ]:
        await db.execute(text(f"DELETE FROM {table}"))
    await db.commit()


async def seed_database(
    db: AsyncSession,
    num_payments: int = 500,
    seed: int | None = 42,
    error_config: ErrorConfig | None = None,
) -> dict:
    await clear_financial_data(db)

    data = generate_synthetic_data(
        num_payments=num_payments,
        seed=seed,
        error_config=error_config,
    )

    for p in data.payments:
        db.add(Payment(
            payment_id=p["payment_id"],
            order_id=p["order_id"],
            amount=p["amount"],
            currency=p["currency"],
            status=p["status"],
            method=p["method"],
            description=p["description"],
            fee=p["fee"],
            tax=p["tax"],
            settlement_id=p["settlement_id"],
            created_at=p["created_at"],
            captured_at=p["captured_at"],
        ))

    for s in data.settlements:
        db.add(Settlement(
            settlement_id=s["settlement_id"],
            amount=s["amount"],
            status=s["status"],
            fees=s["fees"],
            tax=s["tax"],
            utr=s["utr"],
            created_at=s["created_at"],
            settled_at=s["settled_at"],
        ))

    for r in data.refunds:
        db.add(Refund(
            refund_id=r["refund_id"],
            payment_id=r["payment_id"],
            amount=r["amount"],
            status=r["status"],
            created_at=r["created_at"],
        ))

    for d in data.disputes:
        db.add(Dispute(
            dispute_id=d["dispute_id"],
            payment_id=d["payment_id"],
            amount=d["amount"],
            status=d["status"],
            reason_code=d["reason_code"],
            phase=d["phase"],
            respond_by=d["respond_by"],
            created_at=d["created_at"],
        ))

    for b in data.bank_transactions:
        db.add(BankTransaction(
            reference=b["reference"],
            amount=b["amount"],
            type=b["type"],
            date=b["date"],
            description=b["description"],
            balance=b["balance"],
            utr=b["utr"],
        ))

    await db.commit()

    return {
        "payments": len(data.payments),
        "settlements": len(data.settlements),
        "refunds": len(data.refunds),
        "disputes": len(data.disputes),
        "bank_transactions": len(data.bank_transactions),
        "total_records": data.total_records,
        "injected_errors": len(data.injected_errors),
        "error_breakdown": _count_errors(data),
    }


def _count_errors(data: GeneratedData) -> dict:
    counts: dict[str, int] = {}
    for e in data.injected_errors:
        t = e["type"]
        counts[t] = counts.get(t, 0) + 1
    return counts
