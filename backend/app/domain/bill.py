"""Bill as read from a photo, PDF, SMS or typed by the consumer."""

from calendar import monthrange
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ChargeCode = Literal[
    "energy", "fixed", "customer", "duty", "fsa", "true_up", "surcharge", "adjustment", "other"
]
Source = Literal["vision", "sms", "manual"]
Quality = Literal["good", "poor", "unreadable"]
Discom = Literal["TGSPDCL", "TGNPDCL", "OTHER", "UNKNOWN"]


class LineItem(BaseModel):
    code: ChargeCode
    label: str
    amount: float


class UsagePoint(BaseModel):
    """One month from the consumption table many TG bills print."""

    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    units: int = Field(ge=0, le=100_000)


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
    # Net-metered bills print import, export and the billed (net) units; the billed figure is a cross-check.
    billed_units: int | None = None
    load_kw: float | None = None
    # Printed for reference; none of these change the tariff check, but consumers ask about them.
    phase: int | None = Field(default=None, ge=1, le=3)
    multiplying_factor: float | None = None
    recorded_md: float | None = None
    power_factor: float | None = Field(default=None, ge=0, le=1)
    security_deposit: float | None = None
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
        return max(units - (self.export_units or 0), 0)

    def import_units(self) -> int | None:
        """Units drawn from the grid. On a net-metered bill billed plus export is exact, where the faint
        "Import:" figure is the one most often misread."""
        if self.billed_units is not None and self.export_units is not None:
            return self.billed_units + self.export_units
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
