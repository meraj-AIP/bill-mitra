"""Run the rule engine over a bill: compute, audit, predict, advise. Pure, repeatable, cheap."""

from dataclasses import dataclass

from app.domain.audit import AuditResult, audit
from app.domain.bill import ExtractedBill
from app.domain.conversation.facts import Facts, build_facts
from app.domain.insights import Insights, build
from app.domain.prediction import MonthUsage, Prediction, predict
from app.domain.tariff.engine import Computation, compute, has_tariff
from app.store import history as history_store


@dataclass
class Analysis:
    bill: ExtractedBill
    comp: Computation
    audit: AuditResult
    prediction: Prediction
    insights: Insights
    facts: Facts
    history: list[MonthUsage]


def gruha_jyothi_eligible(bill: ExtractedBill) -> bool:
    return bool(bill.gruha_jyothi_household)


def analyse(bill: ExtractedBill, user_id: str) -> Analysis:
    month = bill.month_date()
    load = bill.load_kw or 1.0
    eligible = gruha_jyothi_eligible(bill)
    # A non-domestic bill from before LT-II rates were loaded is priced as before and reported not checkable.
    category = bill.tariff_category() if has_tariff(month, bill.tariff_category()) else "domestic"
    comp = compute(bill.net_units(), month, load, eligible, bill.period(), category, bill.import_units())
    result = audit(bill, comp)
    past = history_store.history(bill, user_id, load, eligible, category)
    pred = predict(month, comp.units, past, eligible, load, category)
    ins = build(month, comp.units, comp.net, load, eligible, past, category)
    facts = build_facts(bill, comp, result, pred, ins)
    return Analysis(bill=bill, comp=comp, audit=result, prediction=pred, insights=ins, facts=facts, history=past)
