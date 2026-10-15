"""The flat set of facts the explanation is allowed to use, and number formatting."""

from datetime import date

from pydantic import BaseModel

from app.domain.audit import AuditResult
from app.domain.bill import ExtractedBill
from app.domain.insights import Insights
from app.domain.prediction import Prediction
from app.domain.tariff.engine import Computation
from app.domain.tariff.tables import version_for


class Facts(BaseModel):
    month: str
    month_number: int
    year: int
    discom: str
    units: int
    export_units: int | None
    group: str
    net: float
    gross: float
    energy: float
    fixed: float
    customer: float
    duty: float
    fsa: float
    true_up: float | None
    bill_amount: float  # this month's amount as printed; the engine's tariff total when nothing is printed
    surcharge: float | None
    arrears: float
    total_payable: float
    audit_status: str
    overcharge: float
    over_lines: list[tuple[str, float]]
    is_domestic: bool
    gj_household: bool
    gj_applied: bool
    gj_lost: bool
    subsidy: float
    delta_units: int | None
    delta_amount: float | None
    pred_month_number: int | None
    pred_low: int | None
    pred_high: int | None
    pred_amount: float | None
    crosses: int | None
    save_cut: int | None
    save_target: int | None
    save_amount: float | None
    ac_minutes: int | None
    cliff_100: float
    cliff_200: float
    due_date: str | None
    rates: list[float]


def build_facts(bill: ExtractedBill, comp: Computation, result: AuditResult,
                pred: Prediction | None, ins: Insights) -> Facts:
    month = bill.month_date()
    true_up = bill.item("true_up")
    printed_current = bill.bill_amount if bill.bill_amount is not None else comp.net + (true_up or 0)
    total = bill.total_payable if bill.total_payable is not None else printed_current + bill.arrears
    cliff = {c.threshold: c.jump for c in ins.cliffs}
    version = version_for(month)
    rates = sorted({s.rate for g in version.groups for s in g.slabs})
    return Facts(
        month=bill.bill_month or month.strftime("%Y-%m"), month_number=month.month, year=month.year,
        discom=bill.discom, units=comp.units, export_units=bill.export_units, group=comp.group,
        net=comp.net, gross=comp.gross, energy=comp.energy, fixed=comp.fixed, customer=comp.customer,
        duty=comp.duty, fsa=comp.fsa, true_up=true_up, bill_amount=round(printed_current, 2),
        surcharge=bill.item("surcharge") or None, arrears=bill.arrears, total_payable=round(total, 2),
        audit_status=result.status, overcharge=result.overcharge,
        over_lines=[(line.code, line.difference or 0) for line in result.lines if line.status == "over"],
        is_domestic=bill.is_domestic, gj_household=bool(bill.gruha_jyothi_household),
        gj_applied=comp.gruha_jyothi_applied, gj_lost="gruha_jyothi_lost" in result.notes,
        subsidy=comp.subsidy,
        delta_units=ins.comparison.delta_units if ins.comparison else None,
        delta_amount=ins.comparison.delta_amount if ins.comparison else None,
        pred_month_number=int(pred.month[5:]) if pred else None,
        pred_low=pred.units_low if pred else None, pred_high=pred.units_high if pred else None,
        pred_amount=pred.amount if pred else None, crosses=pred.crosses if pred else None,
        save_cut=ins.saving.cut_units if ins.saving else None,
        save_target=ins.saving.target_units if ins.saving else None,
        save_amount=ins.saving.saving if ins.saving else None,
        ac_minutes=ins.saving.ac_minutes_per_day if ins.saving else None,
        cliff_100=cliff.get(100, 0.0), cliff_200=cliff.get(200, 0.0),
        due_date=bill.due_date, rates=rates,
    )


def rs(value: float | None) -> str:
    """Indian digit grouping, no trailing .00."""
    if value is None:
        return "0"
    negative = value < 0
    value = abs(round(value, 2))
    whole = int(value)
    paise = round((value - whole) * 100)
    digits = str(whole)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    text = digits if paise == 0 else f"{digits}.{paise:02d}"
    return f"-{text}" if negative else text


def due_label(facts: Facts) -> str | None:
    if not facts.due_date:
        return None
    try:
        d = date.fromisoformat(facts.due_date)
    except ValueError:
        return facts.due_date
    return f"{d.day:02d}-{d.month:02d}-{d.year}"
