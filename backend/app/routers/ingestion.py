from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.models.financial import BankTransaction, Payment
from app.services.auth import get_current_user
from app.services.adapters.razorpay_adapter import RazorpayAdapter
from app.services.adapters.bank_csv_adapter import BankCSVAdapter
from app.services.adapters.internal_csv_adapter import InternalCSVAdapter
from app.services.csv_export import export_bank_csv, export_internal_csv, export_settlements_csv

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


@router.post("/razorpay")
async def ingest_razorpay(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    adapter = RazorpayAdapter(db)
    records = await adapter.fetch()

    by_type: dict[str, int] = {}
    for r in records:
        by_type[r.transaction_type] = by_type.get(r.transaction_type, 0) + 1

    return {
        "source": "razorpay",
        "total_records": len(records),
        "by_type": by_type,
    }


@router.post("/bank-csv")
async def ingest_bank_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    content = (await file.read()).decode("utf-8-sig")
    adapter = BankCSVAdapter(content)

    errors = await adapter.validate()
    if errors:
        raise HTTPException(status_code=422, detail={"validation_errors": errors})

    records = await adapter.fetch()

    from sqlalchemy import text
    await db.execute(text("DELETE FROM bank_transactions"))

    for r in records:
        db.add(BankTransaction(
            reference=r.reference_id,
            amount=r.amount,
            type="credit" if r.transaction_type == "bank_credit" else "debit",
            date=r.date,
            description=r.description,
            balance=r.metadata.get("balance"),
            utr=r.utr,
        ))
    await db.commit()

    return {
        "source": "bank_csv",
        "filename": file.filename,
        "records_imported": len(records),
    }


@router.post("/internal-csv")
async def ingest_internal_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    content = (await file.read()).decode("utf-8-sig")
    adapter = InternalCSVAdapter(content)

    errors = await adapter.validate()
    if errors:
        raise HTTPException(status_code=422, detail={"validation_errors": errors})

    records = await adapter.fetch()

    return {
        "source": "internal_csv",
        "filename": file.filename,
        "records_parsed": len(records),
        "by_type": _count_types(records),
    }


@router.post("/validate/bank-csv")
async def validate_bank_csv(
    file: UploadFile = File(...),
    _current_user: User = Depends(get_current_user),
):
    content = (await file.read()).decode("utf-8-sig")
    adapter = BankCSVAdapter(content)
    errors = await adapter.validate()
    return {"valid": len(errors) == 0, "errors": errors}


@router.post("/validate/internal-csv")
async def validate_internal_csv(
    file: UploadFile = File(...),
    _current_user: User = Depends(get_current_user),
):
    content = (await file.read()).decode("utf-8-sig")
    adapter = InternalCSVAdapter(content)
    errors = await adapter.validate()
    return {"valid": len(errors) == 0, "errors": errors}


@router.get("/export/bank-csv")
async def download_bank_csv(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    content = await export_bank_csv(db)
    return PlainTextResponse(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bank_statement.csv"},
    )


@router.get("/export/internal-csv")
async def download_internal_csv(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    content = await export_internal_csv(db)
    return PlainTextResponse(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=internal_transactions.csv"},
    )


@router.get("/export/settlements-csv")
async def download_settlements_csv(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    content = await export_settlements_csv(db)
    return PlainTextResponse(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=settlements.csv"},
    )


def _count_types(records) -> dict:
    counts: dict[str, int] = {}
    for r in records:
        counts[r.transaction_type] = counts.get(r.transaction_type, 0) + 1
    return counts
