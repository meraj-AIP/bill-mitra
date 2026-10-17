"""Demo complaints for a development server, so the console has a month of realistic work to show.

    python -m app.tools.demo_complaints seed     # replaces any earlier demo rows
    python -m app.tools.demo_complaints remove

Refuses when APP_ENV=production. Every row carries demo = 1 (bills: source = 'demo'), service numbers are fake (99
prefix) and contact numbers are 9999999xxx. No names. Every rupee figure in a description or on a bill comes from
the tariff engine. Section names follow the structure seen on TGSPDCL bills (Isnapur and Kondapur sections under
the Sangareddy ERO); TGNPDCL rows sit in the DISCOM queue.
"""

import secrets
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.core.hashing import mobile_hash, service_hash
from app.domain.bill import ExtractedBill, LineItem
from app.domain.complaint_reply import request_text
from app.domain.conversation.facts import rs
from app.domain.conversation.lang import text
from app.domain.pricing import price
from app.flows import intake
from app.services.notify import status_label
from app.store import complaints, demo, repos, units
from app.store.complaints import General, Placement
from app.store.db import DISCOM_UNITS, connection

CATEGORY = "1B(i) DOMESTIC"
UNIT_TREE = (("circle", "Sangareddy", "DEMO-C-SGR"), ("division", "Sangareddy", "DEMO-D-SGR"),
             ("subdivision", "Patancheru", "DEMO-S-PTC"), ("ero", "Sangareddy", "DEMO-E-SGR"))
SECTIONS = (("Isnapur", "DEMO-SEC-ISN"), ("Kondapur", "DEMO-SEC-KDP"))


@dataclass(frozen=True)
class Spec:
    type: str
    discom: str
    section: str | None  # "Isnapur", "Kondapur" or None for the DISCOM queue
    source: str
    status: str
    days_ago: int
    words: str  # the raiser's words; {units}, {amount}, {usual}, {usual_amount} come from the engine
    units: int | None = None
    usual: int | None = None
    language: str = "en"
    reply: str | None = None
    escalated: bool = False


SPECS: tuple[Spec, ...] = (
    Spec("high_bill", "TGSPDCL", "Isnapur", "whatsapp", "Open", 2,
         "ఈ నెల {units} యూనిట్లకు రూ. {amount} వచ్చింది. మామూలుగా {usual} యూనిట్లే వస్తాయి.", 312, 140, "te"),
    Spec("high_bill", "TGSPDCL", "Kondapur", "consumer_web", "In progress", 6,
         "Bill for {units} units came to Rs {amount}. We usually use about {usual} units (about Rs {usual_amount}).",
         268, 150, reply="We are checking the reading against the meter. A lineman will visit this week."),
    Spec("high_bill", "TGSPDCL", "Isnapur", "call_centre", "Resolved", 21,
         "Caller says the bill of Rs {amount} for {units} units is too high for a two room house.", 205, 180,
         reply="The charges match the tariff for the units read. {units} units crossed the 200 unit step."),
    Spec("high_bill", "TGNPDCL", None, "whatsapp", "Open", 9,
         "Bill is Rs {amount} for {units} units. Last summer it was never more than {usual} units.", 356, 190),
    Spec("high_bill", "TGSPDCL", "Kondapur", "consumer_chat", "Rejected", 27,
         "Rs {amount} for {units} units is too much.", 174, 160,
         reply="The bill is correct: {units} units at the domestic tariff come to Rs {amount}."),
    Spec("wrong_reading", "TGSPDCL", "Isnapur", "consumer_web", "Open", 1,
         "The present reading on my bill is higher than what my meter shows today."),
    Spec("wrong_reading", "TGNPDCL", None, "office", "Open", 4,
         "Walk-in says the reading printed is from the neighbour's meter."),
    Spec("estimated_bill", "TGSPDCL", "Kondapur", "whatsapp", "In progress", 5,
         "Meter reader did not come. The bill says {units} units, Rs {amount}, which looks estimated.", 240, 150,
         reply="The reader will take an actual reading on the next round and the bill will be adjusted."),
    Spec("estimated_bill", "TGSPDCL", "Isnapur", "call_centre", "Open", 11,
         "Caller says the last three bills were the same {units} units. Looks estimated.", 190, None),
    Spec("wrong_category", "TGSPDCL", "Kondapur", "consumer_web", "Open", 12,
         "My house is billed as commercial (LT-II). It is only a home, no shop."),
    Spec("payment_not_updated", "TGSPDCL", "Isnapur", "whatsapp", "Open", 9,
         "Paid Rs {amount} on the TG app, but the new bill still shows it as arrears.", 150, None,
         escalated=True),
    Spec("payment_not_updated", "TGNPDCL", None, "call_centre", "Resolved", 16,
         "Caller paid Rs {amount} at the e-Seva centre. Not reflected in the bill.", 120, None,
         reply="The payment is now posted. It will show on the next bill."),
    Spec("arrears_dispute", "TGSPDCL", "Kondapur", "consumer_web", "In progress", 8,
         "Arrears of Rs {amount} added this month, but every earlier bill was paid on time.", 210, None,
         reply="We are matching the payment history with the billing records."),
    Spec("arrears_dispute", "TGSPDCL", "Isnapur", "office", "Open", 3,
         "Walk-in with receipts says the old dues of Rs {amount} were already cleared.", 160, None),
    Spec("bill_not_received", "TGSPDCL", "Isnapur", "whatsapp", "Resolved", 14,
         "No bill this month. I need it to pay before the due date.",
         reply="The bill was generated. You can also see it on the TGSPDCL website with your service number."),
    Spec("bill_not_received", "TGNPDCL", None, "consumer_chat", "Open", 2,
         "Bill not received for this month."),
    Spec("meter_issue", "TGSPDCL", "Kondapur", "field", "In progress", 4,
         "Meter display blank at the house, seen during the round. Needs a check."),
    Spec("meter_issue", "TGSPDCL", "Isnapur", "whatsapp", "Open", 6,
         "మీటర్ డిస్ప్లే వారం నుంచి ఏమీ చూపించడం లేదు.", language="te"),
    Spec("meter_burnt", "TGSPDCL", "Isnapur", "call_centre", "Open", 5,
         "Caller says the meter burnt after a short circuit. Supply is off.", escalated=True),
    Spec("meter_burnt", "TGNPDCL", None, "whatsapp", "Resolved", 19,
         "Meter burnt last night. Please replace.", reply="The meter was replaced today."),
    Spec("power_outage", "TGSPDCL", "Kondapur", "whatsapp", "In progress", 0,
         "పొద్దున్నుంచి ఇంట్లో కరెంటు లేదు. పక్క ఇళ్లలో ఉంది.", language="te",
         reply="The lineman is on the way. The fuse at the pole has blown."),
    Spec("voltage_fluctuation", "TGSPDCL", "Isnapur", "consumer_web", "Open", 7,
         "Voltage drops every evening. Fans run slow and the fridge keeps tripping."),
    Spec("voltage_fluctuation", "TGNPDCL", None, "call_centre", "In progress", 10,
         "Several houses on the street report low voltage after 7 pm.",
         reply="The transformer load is being checked."),
    Spec("supply_other", "TGSPDCL", "Kondapur", "consumer_chat", "Open", 13,
         "Power goes off five or six times a day for the last week."),
)


def _ts(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _tree() -> dict[str, str]:
    """circle > division > subdivision, with the ERO under the division. Reused when an earlier seed made it."""
    ids: dict[str, str] = {}
    parent = DISCOM_UNITS["TGSPDCL"]
    for kind, name, code in UNIT_TREE:
        found = units.by_code(code)
        unit = found[0] if found else units.create(kind, name, code, ids["division"] if kind == "ero" else parent)
        ids[kind] = unit.id
        if kind != "ero":
            parent = unit.id
    return ids


def _sections() -> dict[str, str]:
    """The Isnapur and Kondapur section ids, creating a small demo tree under TGSPDCL when they do not exist."""
    found = {name: units.match_section("TGSPDCL", name) for name, _ in SECTIONS}
    if all(found.values()):
        return {k: v for k, v in found.items() if v}
    ids = _tree()
    for name, code in SECTIONS:
        if not found[name]:
            match = units.by_code(code)
            found[name] = match[0].id if match else units.create("section", name, code, ids["subdivision"],
                                                                 ids["ero"]).id
    return {k: v for k, v in found.items() if v}


def _bill(spec: Spec, units_: int, service_number: str, month: str, section: str | None) -> ExtractedBill:
    """A synthetic bill priced by the engine: every printed charge is the engine's own figure."""
    shell = ExtractedBill(discom=spec.discom, service_number=service_number, section=section, category=CATEGORY,  # type: ignore[arg-type]
                          bill_month=month, units=units_, load_kw=2.0, gruha_jyothi_household=False,
                          previous_reading=5000.0, present_reading=5000.0 + units_, billing_days=30)
    comp = price(shell, units_, units_)
    lines = [LineItem(code=code, label=code.title(), amount=amount)  # type: ignore[arg-type]
             for code, amount in comp.charges().items()]
    total = float(round(comp.net))
    return shell.model_copy(update={"line_items": lines, "bill_amount": total, "total_payable": total})


def _words(spec: Spec, bill: ExtractedBill | None) -> str:
    if spec.units is None:
        return spec.words
    usual = price(bill, spec.usual, spec.usual).net if bill and spec.usual else 0.0
    amount = bill.bill_amount if bill else 0.0
    return spec.words.format(units=spec.units, amount=rs(amount or 0.0), usual=spec.usual or "",
                             usual_amount=rs(round(usual)))


def _one(spec: Spec, n: int, sections: dict[str, str], now: datetime) -> str:
    created = now - timedelta(days=spec.days_ago, hours=3 + n % 7)
    service_number = f"99{secrets.randbelow(10**10):010d}"
    contact = f"9999999{n:03d}"
    user_id = f"demo:{secrets.token_hex(6)}"
    section_id = sections.get(spec.section or "")
    bill = _bill(spec, spec.units, service_number, f"{created:%Y-%m}", spec.section) if spec.units else None
    bill_id = repos.save_bill(user_id, bill, None, "verified", 0.0, source="demo") if bill else None
    words = _words(spec, bill)
    whatsapp = spec.source == "whatsapp"
    record = General(user_id=user_id, discom=spec.discom, issue=intake.issue_text(spec.type, words),
                     language=spec.language, channel="whatsapp" if whatsapp else "web",
                     reply_to=f"91{contact}" if whatsapp else None, bill_id=bill_id,
                     service_masked=f"••••••••{service_number[-4:]}", bill_month=f"{created:%Y-%m}" if bill else None,
                     section_name=spec.section)
    staff = spec.source in ("call_centre", "office", "field")
    form = complaints.intake_for(spec.type, spec.source, spec.discom, created=created, demo=True,
                                 service_number_hash=service_hash(service_number), description=words,
                                 contact_hash=mobile_hash(contact) if whatsapp or staff else None,
                                 ownership="verified" if bill else "unverified")
    placement = Placement(section_id=section_id, unit_id=section_id or DISCOM_UNITS[spec.discom])
    ticket = complaints.create_general(record, placement, form, words, "officer" if staff else "consumer",
                                       None, _ts(created))
    _thread(ticket, spec, created, words, bill)
    return ticket


def _thread(ticket: str, spec: Spec, created: datetime, words: str, bill: ExtractedBill | None) -> None:
    last = created
    if spec.type == "wrong_reading":
        last = created + timedelta(minutes=2)
        demo.add_message(ticket, "system", request_text("bill_photo", spec.language, ticket), _ts(last))
    if spec.reply:
        last = created + timedelta(hours=20)
        reply = spec.reply.format(units=spec.units, amount=rs(bill.bill_amount or 0.0) if bill else "")
        demo.add_message(ticket, "officer", reply, _ts(last))
    if spec.status != "Open":
        last += timedelta(hours=1)
        line = text(spec.language, "complaint_status", ticket=ticket, status=status_label(spec.language, spec.status))
        demo.add_message(ticket, "system", line, _ts(last))
    escalated = None
    if spec.escalated:
        escalated = _ts(created + timedelta(days=4))
        demo.add_message(ticket, "system", "Escalated for a faster check.", escalated)
        demo.audit_system(ticket, "case.escalate", "to the division, open 4 days", escalated)
        last = max(last, created + timedelta(days=4))
    demo.finish(ticket, spec.status, _ts(last), escalated)


def seed() -> list[tuple[str, int]]:
    demo.remove()
    sections = _sections()
    now = datetime.now(UTC)
    for n, spec in enumerate(SPECS):
        _one(spec, n, sections, now)
    return demo.counts()


def main(argv: list[str]) -> int:
    if get_settings().app_env == "production":
        print("Refused: demo complaints are for development servers only (APP_ENV=production).")
        return 2
    if len(argv) != 1 or argv[0] not in ("seed", "remove"):
        print("Usage: python -m app.tools.demo_complaints seed|remove")
        return 1
    connection()
    if argv[0] == "remove":
        removed, bills = demo.remove()
        print(f"Removed {removed} demo complaints and {bills} demo bills.")
        return 0
    counts = seed()
    print(f"Seeded {sum(c for _, c in counts)} demo complaints: " + ", ".join(f"{t} {c}" for t, c in counts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
