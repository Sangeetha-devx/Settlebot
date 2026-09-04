from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.financial import Payment, Settlement, Refund, Dispute
from app.services.adapters.base import (
    BaseAdapter, CanonicalTransaction, DataSource, TransactionType,
)


class RazorpayAdapter(BaseAdapter):
    """
    Reads from the local DB tables that mirror Razorpay API responses.
    Swap this class to hit live Razorpay APIs by changing fetch() to use httpx.
    """

    source = DataSource.RAZORPAY

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate(self, raw_data=None) -> list[str]:
        return []

    async def fetch(self, **kwargs) -> list[CanonicalTransaction]:
        records: list[CanonicalTransaction] = []
        records.extend(await self._fetch_payments())
        records.extend(await self._fetch_settlements())
        records.extend(await self._fetch_refunds())
        records.extend(await self._fetch_disputes())
        return records

    async def _fetch_payments(self) -> list[CanonicalTransaction]:
        result = await self.db.execute(select(Payment))
        rows = result.scalars().all()
        out = []
        for p in rows:
            out.append(CanonicalTransaction(
                source=self.source.value,
                source_id=p.payment_id,
                transaction_type=TransactionType.PAYMENT.value,
                amount=p.amount,
                currency=p.currency or "INR",
                date=p.created_at,
                status=p.status,
                reference_id=p.order_id,
                settlement_id=p.settlement_id,
                method=p.method,
                fee=p.fee or 0.0,
                tax=p.tax or 0.0,
                description=p.description,
                metadata={"captured_at": str(p.captured_at) if p.captured_at else None},
            ))
        return out

    async def _fetch_settlements(self) -> list[CanonicalTransaction]:
        result = await self.db.execute(select(Settlement))
        rows = result.scalars().all()
        out = []
        for s in rows:
            out.append(CanonicalTransaction(
                source=self.source.value,
                source_id=s.settlement_id,
                transaction_type=TransactionType.SETTLEMENT.value,
                amount=s.amount,
                date=s.settled_at or s.created_at,
                status=s.status,
                fee=s.fees or 0.0,
                tax=s.tax or 0.0,
                utr=s.utr,
                metadata={"created_at": str(s.created_at)},
            ))
        return out

    async def _fetch_refunds(self) -> list[CanonicalTransaction]:
        result = await self.db.execute(select(Refund))
        rows = result.scalars().all()
        return [
            CanonicalTransaction(
                source=self.source.value,
                source_id=r.refund_id,
                transaction_type=TransactionType.REFUND.value,
                amount=r.amount,
                date=r.created_at,
                status=r.status,
                parent_id=r.payment_id,
            )
            for r in rows
        ]

    async def _fetch_disputes(self) -> list[CanonicalTransaction]:
        result = await self.db.execute(select(Dispute))
        rows = result.scalars().all()
        return [
            CanonicalTransaction(
                source=self.source.value,
                source_id=d.dispute_id,
                transaction_type=TransactionType.DISPUTE.value,
                amount=d.amount,
                date=d.created_at,
                status=d.status,
                parent_id=d.payment_id,
                metadata={
                    "reason_code": d.reason_code,
                    "phase": d.phase,
                    "respond_by": str(d.respond_by) if d.respond_by else None,
                },
            )
            for d in rows
        ]
