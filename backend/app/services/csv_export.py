import csv
import io
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.financial import Payment, Settlement, BankTransaction


async def export_bank_csv(db: AsyncSession) -> str:
    result = await db.execute(select(BankTransaction).order_by(BankTransaction.date))
    rows = result.scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "description", "amount", "type", "reference", "utr", "balance"])
    for r in rows:
        writer.writerow([
            r.date.strftime("%Y-%m-%d %H:%M:%S") if r.date else "",
            r.description or "",
            f"{r.amount:.2f}",
            r.type or "credit",
            r.reference or "",
            r.utr or "",
            f"{r.balance:.2f}" if r.balance is not None else "",
        ])
    return buf.getvalue()


async def export_internal_csv(db: AsyncSession) -> str:
    result = await db.execute(
        select(Payment).where(Payment.status == "captured").order_by(Payment.created_at)
    )
    rows = result.scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["transaction_id", "order_id", "amount", "date", "status", "method", "description", "fee", "tax", "type"])
    for p in rows:
        writer.writerow([
            p.payment_id,
            p.order_id or "",
            f"{p.amount:.2f}",
            p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else "",
            p.status or "",
            p.method or "",
            p.description or "",
            f"{p.fee:.2f}" if p.fee else "0.00",
            f"{p.tax:.2f}" if p.tax else "0.00",
            "payment",
        ])
    return buf.getvalue()


async def export_settlements_csv(db: AsyncSession) -> str:
    result = await db.execute(select(Settlement).order_by(Settlement.created_at))
    rows = result.scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["settlement_id", "amount", "status", "fees", "tax", "utr", "created_at", "settled_at"])
    for s in rows:
        writer.writerow([
            s.settlement_id,
            f"{s.amount:.2f}",
            s.status or "",
            f"{s.fees:.2f}" if s.fees else "0.00",
            f"{s.tax:.2f}" if s.tax else "0.00",
            s.utr or "",
            s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else "",
            s.settled_at.strftime("%Y-%m-%d %H:%M:%S") if s.settled_at else "",
        ])
    return buf.getvalue()
