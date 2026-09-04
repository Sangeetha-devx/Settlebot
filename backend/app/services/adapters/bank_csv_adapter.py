import csv
import io
from datetime import datetime
from app.services.adapters.base import (
    BaseAdapter, CanonicalTransaction, DataSource, TransactionType,
)

REQUIRED_COLUMNS = {"date", "description", "amount", "type"}
OPTIONAL_COLUMNS = {"reference", "utr", "balance"}

DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
]


def _parse_date(value: str) -> datetime | None:
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_float(value: str) -> float:
    cleaned = value.strip().replace(",", "").replace("₹", "").replace("INR", "").strip()
    if not cleaned or cleaned == "-":
        return 0.0
    return float(cleaned)


class BankCSVAdapter(BaseAdapter):
    source = DataSource.BANK

    def __init__(self, csv_content: str):
        self.csv_content = csv_content

    async def validate(self, raw_data=None) -> list[str]:
        errors = []
        content = raw_data or self.csv_content
        try:
            reader = csv.DictReader(io.StringIO(content))
            if reader.fieldnames is None:
                return ["CSV file is empty or has no header row"]

            headers = {h.strip().lower() for h in reader.fieldnames}
            missing = REQUIRED_COLUMNS - headers
            if missing:
                errors.append(f"Missing required columns: {', '.join(sorted(missing))}")
                return errors

            row_count = 0
            for i, row in enumerate(reader, start=2):
                row_count += 1
                norm = {k.strip().lower(): v for k, v in row.items()}

                if not norm.get("date", "").strip():
                    errors.append(f"Row {i}: missing date")
                elif _parse_date(norm["date"]) is None:
                    errors.append(f"Row {i}: unrecognized date format '{norm['date']}'")

                if not norm.get("amount", "").strip():
                    errors.append(f"Row {i}: missing amount")
                else:
                    try:
                        _parse_float(norm["amount"])
                    except ValueError:
                        errors.append(f"Row {i}: invalid amount '{norm['amount']}'")

                txn_type = norm.get("type", "").strip().lower()
                if txn_type not in ("credit", "debit", "cr", "dr"):
                    errors.append(f"Row {i}: type must be credit/debit, got '{txn_type}'")

            if row_count == 0:
                errors.append("CSV has headers but no data rows")
        except Exception as e:
            errors.append(f"Failed to parse CSV: {str(e)}")
        return errors

    async def fetch(self, **kwargs) -> list[CanonicalTransaction]:
        reader = csv.DictReader(io.StringIO(self.csv_content))
        records = []
        for i, row in enumerate(reader):
            norm = {k.strip().lower(): v for k, v in row.items()}

            amount = _parse_float(norm.get("amount", "0"))
            txn_type = norm.get("type", "").strip().lower()
            is_credit = txn_type in ("credit", "cr")
            date = _parse_date(norm.get("date", ""))
            description = norm.get("description", "").strip()
            reference = norm.get("reference", "").strip()
            utr = norm.get("utr", "").strip()
            balance = None
            if norm.get("balance", "").strip():
                try:
                    balance = _parse_float(norm["balance"])
                except ValueError:
                    pass

            canonical_type = TransactionType.BANK_CREDIT.value if is_credit else TransactionType.BANK_DEBIT.value

            records.append(CanonicalTransaction(
                source=self.source.value,
                source_id=reference or f"bank_row_{i}",
                transaction_type=canonical_type,
                amount=amount,
                date=date,
                description=description,
                utr=utr or None,
                reference_id=reference or None,
                metadata={"balance": balance, "original_type": txn_type},
            ))
        return records
