"""The complaint types a consumer or staff member can raise. Fixed in code; labels in every language live in the
language packs under `ctype_<code>` (full label) and `ctypeshort_<code>` (a list row title, 24 characters max)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

Category = Literal["billing", "meter", "supply"]
Priority = Literal["urgent", "high", "normal", "low"]
Route = Literal["section", "division", "review"]
Source = Literal["consumer_web", "consumer_chat", "whatsapp", "call_centre", "office", "field"]
Ownership = Literal["verified", "unverified", "not_needed"]
TypeCode = Literal["high_bill", "wrong_reading", "estimated_bill", "wrong_category", "payment_not_updated",
                   "arrears_dispute", "bill_not_received", "meter_issue", "meter_burnt", "power_outage",
                   "voltage_fluctuation", "supply_other"]

CATEGORIES: tuple[Category, ...] = ("billing", "meter", "supply")
PRIORITY_RANK: dict[str, int] = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
WRONG_READING = "wrong_reading"
LEGACY_GENERAL = "high_bill"  # general complaints recorded before types existed were all about the bill amount


@dataclass(frozen=True)
class ComplaintType:
    code: str
    category: Category
    label: str
    needs_bill: bool
    priority: Priority
    target_days: int | None  # None: the review policy's decision SLA applies
    route: Route

    @property
    def label_key(self) -> str:
        return f"ctype_{self.code}"

    @property
    def short_key(self) -> str:
        return f"ctypeshort_{self.code}"


def _t(code: str, category: Category, label: str, priority: Priority, days: int | None,
       route: Route = "section", needs_bill: bool = False) -> ComplaintType:
    return ComplaintType(code, category, label, needs_bill, priority, days, route)


TYPES: tuple[ComplaintType, ...] = (
    _t("high_bill", "billing", "Bill is too high", "normal", 7),
    _t("wrong_reading", "billing", "Meter reading on the bill is wrong", "normal", None, "review", needs_bill=True),
    _t("estimated_bill", "billing", "Bill was estimated, meter not read", "normal", 7),
    _t("wrong_category", "billing", "Wrong tariff category or load", "normal", 15),
    _t("payment_not_updated", "billing", "Payment made but not shown", "high", 3),
    _t("arrears_dispute", "billing", "Arrears or old dues are wrong", "normal", 7),
    _t("bill_not_received", "billing", "Did not get this month's bill", "low", 7),
    _t("meter_issue", "meter", "Meter not working properly", "high", 3),
    _t("meter_burnt", "meter", "Meter is burnt", "urgent", 1),
    _t("power_outage", "supply", "No power at my home", "urgent", 1),
    _t("voltage_fluctuation", "supply", "Low or fluctuating voltage", "high", 3),
    _t("supply_other", "supply", "Other supply problem (frequent cuts, one phase)", "normal", 7),
)
BY_CODE: dict[str, ComplaintType] = {t.code: t for t in TYPES}


def get(code: str) -> ComplaintType:
    return BY_CODE[code]


def in_category(category: str) -> list[ComplaintType]:
    return [t for t in TYPES if t.category == category]


def due_at(code: str, created: datetime, review_sla_days: int) -> str:
    """When the complaint falls due, as the UTC timestamp SQLite writes, so plain text comparison works."""
    days = BY_CODE[code].target_days
    return (created + timedelta(days=review_sla_days if days is None else days)).strftime("%Y-%m-%d %H:%M:%S")
