import csv
import io
from datetime import datetime
from app.services.adapters.base import (
    BaseAdapter, CanonicalTransaction, DataSource, TransactionType,
)

REQUIRED_COLUMNS = {"transaction_id", "amount", "date"}
OPTIONAL_COLUMNS = {"order_id", "status", "method", "description", "fee", "tax", "type"}

DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
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


class InternalCSVAdapter(BaseAdapter):
    source = DataSource.INTERNAL

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

                if not norm.get("transaction_id", "").strip():
                    errors.append(f"Row {i}: missing transaction_id")

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

            if row_count == 0:
                errors.append("CSV has headers but no data rows")
        except Exception as e:
            errors.append(f"Failed to parse CSV: {str(e)}")
        return errors

    async def fetch(self, **kwargs) -> list[CanonicalTransaction]:
        reader = csv.DictReader(io.StringIO(self.csv_content))
        records = []
        for row in reader:
            norm = {k.strip().lower(): v for k, v in row.items()}

            txn_id = norm.get("transaction_id", "").strip()
            amount = _parse_float(norm.get("amount", "0"))
            date = _parse_date(norm.get("date", ""))
            order_id = norm.get("order_id", "").strip() or None
            status = norm.get("status", "").strip() or None
            method = norm.get("method", "").strip() or None
            description = norm.get("description", "").strip() or None
            fee = _parse_float(norm.get("fee", "0"))
            tax = _parse_float(norm.get("tax", "0"))
            txn_type = norm.get("type", "payment").strip().lower()

            type_map = {
                "payment": TransactionType.PAYMENT.value,
                "refund": TransactionType.REFUND.value,
                "dispute": TransactionType.DISPUTE.value,
                "fee": TransactionType.FEE.value,
            }
            canonical_type = type_map.get(txn_type, TransactionType.PAYMENT.value)

            records.append(CanonicalTransaction(
                source=self.source.value,
                source_id=txn_id,
                transaction_type=canonical_type,
                amount=amount,
                date=date,
                status=status,
                reference_id=order_id,
                method=method,
                fee=fee,
                tax=tax,
                description=description,
            ))
        return records
