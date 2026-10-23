"""Turns engine facts into sentences. Template path; also the fallback for the model path."""

import re

from app.domain import meter_status
from app.domain.conversation.facts import Facts, due_label, rs
from app.domain.conversation.lang import pack, text


def month_label(language: str, month_number: int, year: int) -> str:
    return f"{pack(language).MONTHS[month_number - 1]} {year}"


def _label(language: str, code: str) -> str:
    labels: dict[str, str] = pack(language).LABEL
    return labels.get(code, code)


def _audit_sentences(f: Facts, lang: str) -> list[str]:
    if f.audit_status == "not_checkable":
        return [text(lang, "non_domestic")]
    if f.audit_status == "verified":
        return [text(lang, "verified")]
    if f.audit_status == "calculated":
        return [text(lang, "calculated")]
    if f.audit_status == "mismatch":
        return [text(lang, "mismatch", label=_label(lang, code), diff=rs(diff)) for code, diff in f.over_lines]
    return [text(lang, "partial")]


def _estimated(f: Facts, lang: str, key: str) -> list[str]:
    if not meter_status.estimated(f.reading_status):
        return []
    return [text(lang, key, code=f.reading_status, why=text(lang, f"sts_{meter_status.kind(f.reading_status)}"))]


def _prediction_sentences(f: Facts, lang: str) -> list[str]:
    if f.pred_low is None or f.pred_amount is None:
        return []
    out = [text(lang, "prediction", low=f.pred_low, high=f.pred_high, amount=rs(f.pred_amount))]
    if f.crosses == 200 and f.gj_household:
        out.append(text(lang, "warn_gj"))
    elif f.crosses:
        out.append(text(lang, "warn_cross", t=f.crosses))
    return out


def explain(f: Facts, lang: str) -> list[str]:
    """Spoken explanation, in the order a person would say it."""
    month = month_label(lang, f.month_number, f.year)
    out = [text(lang, "headline", month=month, units=f.units, net=rs(f.bill_amount))]
    if f.arrears > 0:
        out.append(text(lang, "arrears_total", arrears=rs(f.arrears), total=rs(f.total_payable)))
    elif f.arrears < 0:
        out.append(text(lang, "credit_total", credit=rs(-f.arrears), total=rs(f.total_payable)))
    if f.export_units:
        out.append(text(lang, "net_metering", export=f.export_units, units=f.units))
    if f.audit_status != "not_checkable":
        out.append(text(lang, f"group_{f.group}"))
    if f.gj_applied:
        out.append(text(lang, "gj_applied", subsidy=rs(f.subsidy)))
    elif f.gj_lost:
        out.append(text(lang, "gj_lost"))
    out.extend(_audit_sentences(f, lang))
    if f.tariff_nearest:
        out.append(text(lang, "tariff_nearest"))
    out.extend(_estimated(f, lang, "reading_estimated"))
    if f.surcharge:
        out.append(text(lang, "surcharge", surcharge=rs(f.surcharge)))
    if f.delta_units:
        key = "delta_up" if f.delta_units > 0 else "delta_down"
        out.append(text(lang, key, d=abs(f.delta_units)))
    if f.true_up:
        out.append(text(lang, "true_up", true_up=rs(f.true_up)))
    if f.save_cut and f.save_amount:
        out.append(text(lang, "save", cut=f.save_cut, saving=rs(f.save_amount), ac=f.ac_minutes))
    out.extend(_prediction_sentences(f, lang))
    return out


def summary_card(f: Facts, lang: str) -> str:
    """The short text message under the voice note."""
    status = text(lang, f"status_{f.audit_status}", over=rs(f.overcharge))
    lines = [status, text(lang, "card_units", units=f.units, group=f.group),
             text(lang, "card_pay", total=rs(f.total_payable))]
    due = due_label(f)
    if due:
        lines.append(text(lang, "card_due", due=due))
    if f.pred_amount is not None:
        lines.append(text(lang, "card_next", amount=rs(f.pred_amount)))
    return "\n".join(lines)


def why_high(f: Facts, lang: str) -> str:
    reasons = _estimated(f, lang, "reason_estimated")
    if f.overcharge:
        reasons.append(text(lang, "reason_overcharge", over=rs(f.overcharge)))
    if f.units > 200:
        reasons.append(text(lang, "reason_cross200", cliff=rs(f.cliff_200)))
    if f.gj_lost:
        reasons.append(text(lang, "reason_gj"))
    if f.delta_units and f.delta_units > 0:
        reasons.append(text(lang, "reason_delta", d=f.delta_units))
    return " ".join(reasons) if reasons else text(lang, "reason_ok")


def save_advice(f: Facts, lang: str) -> str:
    if f.save_cut and f.save_amount:
        advice = text(lang, "save", cut=f.save_cut, saving=rs(f.save_amount), ac=f.ac_minutes)
        if f.gj_lost:
            advice = f"{advice} {text(lang, 'gj_back')}"
        return advice
    return text(lang, "save_general")


def gruha_jyothi(f: Facts, lang: str) -> str:
    if f.gj_applied:
        return text(lang, "gj_applied", subsidy=rs(f.subsidy))
    if f.gj_lost:
        return f"{text(lang, 'gj_lost')} {text(lang, 'gj_back')}"
    return text(lang, "gj_info")


def due(f: Facts, lang: str) -> str:
    label = due_label(f)
    if not label:
        return text(lang, "due_unknown")
    return text(lang, "due", total=rs(f.total_payable), due=label)


def explain_charge(f: Facts, lang: str, code: str) -> str:
    values = {"fsa": rs(f.fsa), "fixed": rs(f.fixed), "customer": rs(f.customer), "duty": rs(f.duty)}
    return text(lang, f"explain_{code}", **values)


def next_bill(f: Facts, lang: str) -> str:
    sentences = _prediction_sentences(f, lang)
    return " ".join(sentences) or text(lang, "need_bill")


def plain(message: str) -> str:
    """Strip WhatsApp formatting for speech."""
    return re.sub(r"[*_~]", "", message)
