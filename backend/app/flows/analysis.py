"""Run the rule engine over a bill: compute, audit, predict, advise. Pure, repeatable, cheap."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.audit import AuditResult, audit
from app.domain.bill import ExtractedBill
from app.domain.conversation.facts import Facts, build_facts
from app.domain.insights import Insights, build
from app.domain.prediction import MonthUsage, Prediction, predict
from app.domain.pricing import category, gruha_jyothi_eligible, price
from app.domain.tariff.engine import Computation
from app.store import history as history_store

__all__ = ["Analysis", "analyse", "gruha_jyothi_eligible"]


@dataclass
class Analysis:
    bill: ExtractedBill
    comp: Computation
    audit: AuditResult
    prediction: Prediction
    insights: Insights
    facts: Facts
    history: list[MonthUsage]


def analyse(bill: ExtractedBill, user_id: str, discom_months: Sequence[tuple[str, int]] = ()) -> Analysis:
    """discom_months: (YYYY-MM, units) from the DISCOM billing records, known only on a case."""
    month = bill.month_date()
    load = bill.load_kw or 1.0
    eligible = gruha_jyothi_eligible(bill)
    kind = category(bill)
    comp = price(bill, bill.net_units(), bill.import_units())
    result = audit(bill, comp)
    past = history_store.history(bill, user_id, load, eligible, kind, discom_months)
    pred = predict(month, comp.units, past, eligible, load, kind)
    ins = build(month, comp.units, comp.net, load, eligible, past, kind)
    facts = build_facts(bill, comp, result, pred, ins)
    return Analysis(bill=bill, comp=comp, audit=result, prediction=pred, insights=ins, facts=facts, history=past)
