"""Bill as read from a photo, PDF, SMS or typed by the consumer."""

from calendar import monthrange
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ChargeCode = Literal[
    "energy", "fixed", "customer", "duty", "fsa", "true_up", "surcharge", "adjustment", "other"
]
Source = Literal["vision", "sms", "manual"]
Quality = Literal["good", "poor", "unreadable"]
Discom = Literal["TGSPDCL", "TGNPDCL", "OTHER", "UNKNOWN"]


def real_date(value: str | None) -> bool:
    """A YYYY-MM-DD the calendar has. A blurred slip can read 30/02, which the pattern allows."""
    if value is None or len(value) != 10:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def real_month(value: str | None) -> bool:
    """A YYYY-MM the calendar has. The pattern alone lets a misread month 13 through to date()."""
    return value is not None and len(value) == 7 and real_date(f"{value}-01")


def _month_or_none(value: str | None) -> str | None:
    if value is not None and not real_month(value):
        raise ValueError("not a calendar month")
    return value


def _date_or_none(value: str | None) -> str | None:
    if value is not None and not real_date(value):
        raise ValueError("not a calendar date")
    return value


class LineItem(BaseModel):
    code: ChargeCode
    label: str
    amount: float


class UsagePoint(BaseModel):
    """One month from the consumption table many TG bills print."""

    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    units: int = Field(ge=0, le=100_000)

    _real_month = field_validator("month")(_month_or_none)


DocumentType = Literal["bill", "meter", "other"]


class ExtractedBill(BaseModel):
    document_type: DocumentType = "bill"
    is_electricity_bill: bool = True
    meter_reading: float | None = None
    quality: Quality = "good"
    quality_issue: str | None = None
    discom: Discom = "UNKNOWN"
    service_number: str | None = None
    section: str | None = None
    category: str | None = Field(default=None, description="Tariff category as printed, e.g. LT-I(B)")
    is_domestic: bool = True
    bill_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    bill_date: str | None = None
    due_date: str | None = None
    previous_reading_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    billing_days: int | None = Field(default=None, ge=1, le=62)
    previous_reading: float | None = None
    present_reading: float | None = None
    # The two digit "Sts" code beside each reading: 01 is a normal reading, others mean estimated (meter_status.py).
    present_status: str | None = Field(default=None, pattern=r"^\d{2}$")
    previous_status: str | None = Field(default=None, pattern=r"^\d{2}$")
    units: int | None = None
    export_units: int | None = None
    # Net-metered bills print the export register's own readings; their difference is the export.
    export_previous_reading: float | None = None
    export_present_reading: float | None = None
    # Net-metered bills print import, export and the billed (net) units; the billed figure is a cross-check.
    billed_units: int | None = None
    load_kw: float | None = None
    # Printed for reference; none of these change the tariff check, but consumers ask about them.
    phase: int | None = Field(default=None, ge=1, le=3)
    multiplying_factor: float | None = None
    recorded_md: float | None = None
    power_factor: float | None = Field(default=None, ge=0, le=1)
    security_deposit: float | None = None
    # Solar units banked from export, as printed "Prev/Pres CF Units : a/b": a is brought in, b is carried on.
    previous_carry_forward_units: int | None = None
    carry_forward_units: int | None = None
    disconnection_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    last_paid_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    line_items: list[LineItem] = Field(default_factory=list)
    bill_amount: float | None = None
    arrears: float = 0.0
    total_payable: float | None = None
    gruha_jyothi_household: bool | None = None
    subsidy_amount: float | None = None
    usage_history: list[UsagePoint] = Field(default_factory=list)
    unreadable_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.9, ge=0, le=1)
    source: Source = "vision"

    _real_month = field_validator("bill_month")(_month_or_none)
    _real_dates = field_validator("previous_reading_date", "disconnection_date", "last_paid_date")(_date_or_none)

    def month_date(self) -> date:
        if self.bill_month:
            year, month = self.bill_month.split("-")
            return date(int(year), int(month), 1)
        today = date.today()
        return date(today.year, today.month, 1)

    def period(self) -> float:
        """Billing period as a fraction of the month it started in; 1.0 when the bill does not say."""
        if not self.billing_days or not self.previous_reading_date:
            return 1.0
        start = date.fromisoformat(self.previous_reading_date)
        month_days = monthrange(start.year, start.month)[1]
        return min(max(self.billing_days / month_days, 0.5), 2.0)

    def net_units(self) -> int:
        # The printed billed units are the DISCOM's own net figure; import minus export is checked against it.
        if self.billed_units is not None:
            return self.billed_units
        units = self.units or 0
        return max(units - (self.export_units or 0) - (self.previous_carry_forward_units or 0), 0)

    def import_units(self) -> int | None:
        """Units drawn from the grid. On a net-metered bill the printed billed, export and banked units give it
        exactly, where the faint "Import:" figure is the one most often misread: billed + export + banked in when
        something is billed, else export + banked in - banked on (units are carried on only when nothing is billed)."""
        if self.billed_units is not None and self.export_units is not None:
            banked_in = self.previous_carry_forward_units or 0
            if self.billed_units > 0:
                return self.billed_units + self.export_units + banked_in
            return max(self.export_units + banked_in - (self.carry_forward_units or 0), 0)
        return self.units

    def tariff_category(self) -> Literal["domestic", "non_domestic"]:
        return "domestic" if self.is_domestic else "non_domestic"

    def item(self, code: str) -> float | None:
        values = [line.amount for line in self.line_items if line.code == code]
        return round(sum(values), 2) if values else None

    def masked_service_number(self) -> str | None:
        return mask(self.service_number)


def mask(service_number: str | None) -> str | None:
    """Last four digits only, wherever a service number leaves storage."""
    if not service_number:
        return None
    digits = service_number.strip()
    return "•" * max(len(digits) - 4, 0) + digits[-4:]
