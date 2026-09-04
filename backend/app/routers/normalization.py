from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.services.auth import get_current_user
from app.services.adapters.razorpay_adapter import RazorpayAdapter
from app.services.adapters.bank_csv_adapter import BankCSVAdapter
from app.services.adapters.internal_csv_adapter import InternalCSVAdapter
from app.services.normalization import normalize
from app.services.csv_export import export_bank_csv, export_internal_csv

router = APIRouter(prefix="/api/normalization", tags=["normalization"])


@router.post("/run")
async def run_normalization(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    rz_adapter = RazorpayAdapter(db)
    rz_records = await rz_adapter.fetch()

    bank_csv = await export_bank_csv(db)
    bank_adapter = BankCSVAdapter(bank_csv)
    bank_records = await bank_adapter.fetch()

    internal_csv = await export_internal_csv(db)
    internal_adapter = InternalCSVAdapter(internal_csv)
    internal_records = await internal_adapter.fetch()

    all_records = rz_records + bank_records + internal_records

    result = normalize(all_records)

    sample_warnings = result.warnings[:20]

    return {
        "status": "success",
        "total_input": result.total_input,
        "total_output": result.total_output,
        "duplicates_removed": result.duplicates_removed,
        "by_source": result.by_source,
        "by_type": result.by_type,
        "stats": result.stats,
        "warning_count": len(result.warnings),
        "sample_warnings": sample_warnings,
    }


@router.post("/run/razorpay")
async def normalize_razorpay(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    adapter = RazorpayAdapter(db)
    records = await adapter.fetch()
    result = normalize(records)

    return {
        "source": "razorpay",
        "total_input": result.total_input,
        "total_output": result.total_output,
        "duplicates_removed": result.duplicates_removed,
        "by_type": result.by_type,
        "stats": result.stats,
        "warning_count": len(result.warnings),
    }


@router.post("/run/bank")
async def normalize_bank(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    bank_csv = await export_bank_csv(db)
    adapter = BankCSVAdapter(bank_csv)
    records = await adapter.fetch()
    result = normalize(records)

    return {
        "source": "bank",
        "total_input": result.total_input,
        "total_output": result.total_output,
        "duplicates_removed": result.duplicates_removed,
        "by_type": result.by_type,
        "stats": result.stats,
        "warning_count": len(result.warnings),
    }


@router.post("/run/internal")
async def normalize_internal(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    internal_csv = await export_internal_csv(db)
    adapter = InternalCSVAdapter(internal_csv)
    records = await adapter.fetch()
    result = normalize(records)

    return {
        "source": "internal",
        "total_input": result.total_input,
        "total_output": result.total_output,
        "duplicates_removed": result.duplicates_removed,
        "by_type": result.by_type,
        "stats": result.stats,
        "warning_count": len(result.warnings),
    }
