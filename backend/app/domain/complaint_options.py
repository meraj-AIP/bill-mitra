"""Reply options for a complaint, chosen from what was actually asked. No I/O.

An option fits the complaint's type, its status, what the bill check found and where the conversation stands.
Figures appear only in the bill options, and they come from the engine through `complaint_reply.draft` or the
facts. Labels and why lines are English for staff; the text is in the consumer's language.
"""

import re
from dataclasses import dataclass, field

from app.domain import complaint_reply
from app.domain.audit import AuditResult
from app.domain.complaint_reply import AskKind, Triage
from app.domain.complaint_types import BY_CODE, LEGACY_GENERAL
from app.domain.conversation.composer import month_label
from app.domain.conversation.facts import Facts, rs
from app.domain.conversation.lang import text

MAX_OPTIONS = 4
OPEN = ("Open", "In progress")
EXPLAINS_BILL = ("high_bill", "wrong_reading", "estimated_bill", "wrong_category", "arrears_dispute")
NEEDS_PHOTO = ("high_bill", "wrong_reading", "wrong_category")  # nothing to check without the bill itself
# Consumer copy never says who handles a complaint. Checked on every template and on every AI draft.
STAFF_WORDS = re.compile(r"\b(?:officers?|AE|assistant engineer|engineers?|linem[ae]n|staff|crew member)\b"
                         r"|అధికారి|ఇంజనీర్|లైన్‌మ్యాన్|లైన్ మ్యాన్|अधिकारी|इंजीनियर|लाइनमैन|कर्मचारी"
                         r"|افسر|انجینئر|لائن مین|عملہ", re.IGNORECASE)


@dataclass(frozen=True)
class Context:
    """What the options are chosen from. `facts` and `audit` are set only when a checked bill is linked."""

    ticket: str
    type: str
    status: str
    language: str
    facts: Facts | None = None
    audit: AuditResult | None = None
    asked: frozenset[str] = field(default_factory=frozenset)  # every kind we ever asked for
    waiting: frozenset[str] = field(default_factory=frozenset)  # asked and not answered yet
    answered: bool = False  # the consumer's last message came after we wrote to them
    sent_photo: bool = False  # and it carried a photo

    @property
    def triage(self) -> Triage | None:
        return complaint_reply.triage(self.audit) if self.audit else None


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    text: str
    why: str
    asks: AskKind | None = None  # sending this reply also waits for the consumer's answer, like a request


@dataclass(frozen=True)
class AskOption:
    kind: AskKind
    label: str
    text: str
    why: str


# key: (staff label, why it fits). The text is the lang key opt_<key> unless built from the bill or a request.
REPLIES: dict[str, tuple[str, str]] = {
    "photo_thanks": ("Thanks, checking the photo", "The consumer's last message is a photo. Confirm it arrived."),
    "answer_thanks": ("Thanks for the details", "The consumer answered after we wrote. Confirm it arrived."),
    "waiting_reminder": ("Remind them what we asked", "We asked the consumer for something and have no answer yet."),
    "overcharge": ("Explain the overcharge", "The tariff check found charges above the TGERC tariff. Figures are "
                                             "the engine's."),
    "bill_correct": ("Bill is correct", "Every charge matches the TGERC tariff. Units and amount are the engine's."),
    "needs_check": ("Ask for a clearer bill", "The tariff check could not read every charge from the photo."),
    "ask_meter_photo": ("Ask for a meter photo", "The meter display shows the real reading. Not asked yet."),
    "ask_bill_photo": ("Ask for the bill photo", "No bill is linked, so the charges cannot be checked yet."),
    "ask_payment_proof": ("Ask for the payment receipt", "A receipt or transaction reference lets billing trace "
                                                         "the payment. Not asked yet."),
    "ask_earlier_bills": ("Ask for earlier bills", "Earlier bills show where the old dues started. Not asked yet."),
    "high_bill_checking": ("Checking the bill", "No bill to explain yet: say what is being checked."),
    "reading_check": ("Reading is being checked", "A wrong reading goes to the reading check; the bill is revised "
                                                  "only if the reading was wrong."),
    "estimated_adjust": ("Adjusted at the next reading", "An estimated bill is settled when the meter is read."),
    "category_check": ("Checking category and load", "The complaint is about the tariff category or load."),
    "payment_posting": ("Payment is being traced", "Say the payment is being matched and posted. No date promised."),
    "arrears_check": ("Checking the old dues", "The complaint disputes arrears: they are checked against earlier "
                                               "bills and payments."),
    "bill_how_to": ("How to get the bill", "Bill Mitra fetches the bill by service number; the DISCOM office has "
                                           "it too."),
    "bill_delivery_check": ("Delivery is being checked", "The bill did not reach them: note it and check delivery."),
    "meter_visit": ("Meter will be checked on site", "A faulty meter is checked at site and replaced if needed."),
    "meter_burnt_visit": ("Burnt meter will be replaced", "A burnt meter needs a site visit; add the safety line."),
    "crew_informed": ("Field team informed", "A supply problem: the local field team is told."),
    "voltage_check": ("Voltage will be checked", "Low or fluctuating voltage is checked at the transformer and line."),
    "call_1912": ("Call 1912 if urgent", "A supply problem: 1912 is the line for urgent or unsafe supply."),
    "received": ("Received, working on it", "A plain acknowledgement that fits any open complaint."),
    "closing_resolved": ("Closing note", "The complaint is resolved."),
    "closing_rejected": ("Closing note", "The complaint was closed without a change."),
    "closing_followup": ("If it comes back", "Tells them how to come back if the problem returns."),
}
ASK_KEYS: dict[str, AskKind] = {"ask_meter_photo": "meter_photo", "ask_bill_photo": "bill_photo",
                                "ask_payment_proof": "payment_proof", "ask_earlier_bills": "earlier_bills",
                                "needs_check": "bill_photo"}
ASKS: dict[AskKind, tuple[str, str]] = {
    "meter_photo": ("Meter photo", "The meter display shows the real reading to compare with the bill."),
    "bill_photo": ("Full bill photo", "No bill is linked, so the charges cannot be checked yet."),
    "earlier_bills": ("Earlier bills", "Earlier bills show how usage and dues moved month to month."),
    "payment_proof": ("Payment receipt", "A receipt or transaction reference lets billing trace and post it."),
    "details": ("More details", "More about the problem in their own words, for example where and since when."),
}
# What each type may ask the consumer for, most useful first. bill_photo is dropped once a bill is linked.
ASKS_BY_TYPE: dict[str, tuple[AskKind, ...]] = {
    "high_bill": ("meter_photo", "bill_photo", "earlier_bills", "details"),
    "wrong_reading": ("meter_photo", "bill_photo", "earlier_bills"),
    "estimated_bill": ("meter_photo", "bill_photo", "details"),
    "wrong_category": ("bill_photo", "details"),
    "payment_not_updated": ("payment_proof", "details"),
    "arrears_dispute": ("earlier_bills", "payment_proof", "bill_photo"),
    "bill_not_received": ("details",),
    "meter_issue": ("meter_photo", "details"),
    "meter_burnt": ("meter_photo", "details"),
    "power_outage": ("details",),
    "voltage_fluctuation": ("details",),
    "supply_other": ("details",),
}
# The type's own options when no bill changes the picture.
BY_TYPE: dict[str, tuple[str, ...]] = {
    "wrong_reading": ("reading_check", "ask_meter_photo"),
    "estimated_bill": ("estimated_adjust", "ask_meter_photo"),
    "wrong_category": ("category_check",),
    "payment_not_updated": ("ask_payment_proof", "payment_posting"),
    "arrears_dispute": ("arrears_check", "ask_earlier_bills", "ask_payment_proof"),
    "bill_not_received": ("bill_how_to", "bill_delivery_check"),
    "meter_issue": ("meter_visit", "ask_meter_photo"),
    "meter_burnt": ("meter_burnt_visit", "ask_meter_photo"),
    "power_outage": ("crew_informed", "call_1912"),
    "voltage_fluctuation": ("voltage_check", "call_1912"),
    "supply_other": ("crew_informed", "call_1912"),
}


def type_of(code: str | None, kind: str) -> str:
    """Older rows carry no type: a reading check is wrong_reading, anything else was about the bill amount."""
    if code in BY_CODE:
        return code
    return "wrong_reading" if kind == "wrong_reading" else LEGACY_GENERAL


def _bill_keys(ctx: Context) -> list[str]:
    """Only complaints about the bill amount get the bill check; payment, delivery, meter and supply never do."""
    if ctx.type not in EXPLAINS_BILL:
        return []
    if ctx.audit is None:
        return ["ask_bill_photo"] if ctx.type in NEEDS_PHOTO else []
    kind = ctx.triage
    if kind == "overcharge":
        return ["overcharge"]
    if ctx.type != "high_bill":
        return []
    return ["bill_correct", "ask_meter_photo"] if kind == "bill_correct" else ["needs_check"]


def _lead(ctx: Context) -> list[str]:
    if ctx.sent_photo:
        return ["photo_thanks"]
    if ctx.answered:
        return ["answer_thanks"]
    return ["waiting_reminder"] if ctx.waiting else []


def _keys(ctx: Context) -> list[str]:
    if ctx.status not in OPEN:
        return ["closing_resolved" if ctx.status == "Resolved" else "closing_rejected", "closing_followup"]
    keys = _lead(ctx) + _bill_keys(ctx) + list(BY_TYPE.get(ctx.type, ()))
    if ctx.type == "high_bill" and ctx.audit is None:
        keys.append("high_bill_checking")
    # Nothing new to ask while an answer is still owed, and never the same thing twice.
    keys = [k for k in keys if k not in ASK_KEYS or (not ctx.waiting and ASK_KEYS[k] not in ctx.asked)]
    keys = list(dict.fromkeys(keys))[:MAX_OPTIONS]
    return keys if len(keys) >= 2 else [*keys, "received"]


def _text(ctx: Context, key: str) -> str:
    lang = ctx.language
    if key in ("overcharge", "needs_check"):
        assert ctx.facts and ctx.audit
        return complaint_reply.draft(ctx.facts, ctx.audit, lang)
    if key == "bill_correct":
        assert ctx.facts
        return text(lang, "opt_bill_correct", month=month_label(lang, ctx.facts.month_number, ctx.facts.year),
                    units=ctx.facts.units, amount=rs(ctx.facts.bill_amount))
    if key in ASK_KEYS and key != "needs_check":
        return complaint_reply.request_text(ASK_KEYS[key], lang, ctx.ticket)
    return text(lang, f"opt_{key}")


def reply_options(ctx: Context) -> list[Option]:
    """Two to four replies that fit this complaint, the best fit first."""
    return [Option(k, REPLIES[k][0], _text(ctx, k), REPLIES[k][1], ASK_KEYS.get(k)) for k in _keys(ctx)]


def allowed_asks(ctx: Context) -> tuple[AskKind, ...]:
    """Every kind of request that makes sense for this type. The request route refuses anything else."""
    kinds = ASKS_BY_TYPE[ctx.type]
    return tuple(k for k in kinds if not (k == "bill_photo" and ctx.audit is not None))


def ask_options(ctx: Context) -> list[AskOption]:
    """Requests that fit the type, minus anything we are still waiting for."""
    if ctx.status not in OPEN:
        return []
    return [AskOption(k, ASKS[k][0], complaint_reply.request_text(k, ctx.language, ctx.ticket), ASKS[k][1])
            for k in allowed_asks(ctx) if k not in ctx.waiting]
