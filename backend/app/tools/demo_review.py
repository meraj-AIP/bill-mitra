"""Demo wrong reading cases for a development server, so the review screens have work the section AE must act on.

Seeded by app.tools.demo_complaints (same seed and remove commands, same production refusal). Nothing here writes a
case by hand: bills are stored with the functions an upload uses (source 'demo'), cases open through the report
path a consumer's "Report a problem" uses, and the decided case goes through the real decision route. So routing,
the evidence pack, the requests for earlier bills, the misread suggestion and the timeline are the system's own.

Fake service numbers (99 prefix), no names, no real bills. Every printed charge is the engine's figure.
"""

import asyncio
import secrets
from datetime import UTC, date, datetime, timedelta

from app.api.review_decisions import DecisionBody, EvidenceRef, decide
from app.domain.bill import ExtractedBill, LineItem, UsagePoint
from app.domain.pricing import price
from app.flows import case_bills, cases, misread
from app.flows.analysis import analyse
from app.store import accounts, complaints, demo, repos
from app.store import case_evidence as evidence_store

LOGIN = "demo.seed.ae@aiplanet.com"
STAFF_NAME = "Demo Seed AE"
DISCOM = "TGSPDCL"
CATEGORY = "1B(i) DOMESTIC"
BILL_DAY = 4  # spot bills in these sections are read early in the month


def _month(back: int) -> date:
    """The first of the month `back` months before the newest bill month. The newest bill is the one read on
    BILL_DAY this month, or last month when that day has not come yet, so the demo never shows a future bill."""
    anchor = datetime.now(UTC).date() - timedelta(days=BILL_DAY + 1)
    index = anchor.year * 12 + anchor.month - 1 - back
    return date(index // 12, index % 12 + 1, 1)


def _usage(back: int, units: list[int]) -> list[UsagePoint]:
    """The printed consumption table: `units` oldest first, ending the month before bill month `back`."""
    return [UsagePoint(month=f"{_month(back + len(units) - i):%Y-%m}", units=u) for i, u in enumerate(units)]


def make_bill(service_number: str, section: str, back: int, previous: int, present: int,
              history: list[int], status: str = "01") -> ExtractedBill:
    """A spot bill for month `back`, read on BILL_DAY, priced by the engine at the units its readings give."""
    start, end = _month(back + 1).replace(day=BILL_DAY), _month(back).replace(day=BILL_DAY)
    units = present - previous
    shell = ExtractedBill(discom=DISCOM, service_number=service_number, section=section, category=CATEGORY,
                          bill_month=f"{end:%Y-%m}", bill_date=end.isoformat(),
                          due_date=(end + timedelta(days=14)).isoformat(), previous_reading_date=start.isoformat(),
                          billing_days=(end - start).days, previous_reading=float(previous),
                          present_reading=float(present), present_status=status, previous_status="01", units=units,
                          load_kw=2.0, gruha_jyothi_household=False, usage_history=_usage(back, history))
    comp = price(shell, units, units)
    lines = [LineItem(code=code, label=code.title(), amount=amount)  # type: ignore[arg-type]
             for code, amount in comp.charges().items()]
    total = float(round(comp.net))
    return shell.model_copy(update={"line_items": lines, "bill_amount": total, "total_payable": total})


def fixed_for_load(bill: ExtractedBill, printed_load: float) -> ExtractedBill:
    """The same bill with only the fixed charge printed for `printed_load` kW instead of the contracted load. Both
    figures are the engine's, so the difference the charges check shows is exact."""
    assert bill.units is not None
    wrong = price(bill.model_copy(update={"load_kw": printed_load}), bill.units, bill.units).fixed
    lines = [line.model_copy(update={"amount": wrong}) if line.code == "fixed" else line for line in bill.line_items]
    total = float(round(sum(line.amount for line in lines)))
    return bill.model_copy(update={"line_items": lines, "bill_amount": total, "total_payable": total})


def _consumer() -> tuple[str, str]:
    return f"demo:{secrets.token_hex(6)}", f"99{secrets.randbelow(10**10):010d}"


def ingest(user_id: str, bill: ExtractedBill) -> str:
    """What a checked upload does once the bill is read: store it, file it under a case that asked for its month,
    and look for a misread on the month before."""
    a = analyse(bill, user_id)
    bill_id = repos.save_bill(user_id, bill, None, a.audit.status, a.audit.overcharge, source="demo")
    case_bills.attach_upload(user_id, bill_id, bill, None)
    misread.after_bill_saved(user_id, bill, bill_id)
    return bill_id


async def _report(user_id: str, bill_id: str, language: str, note: str) -> str:
    """The consumer's "Report a problem with this bill" on the web, as POST /api/bills/{id}/review-request runs it."""
    stored = repos.get_own_bill(user_id, bill_id)
    assert stored is not None
    ticket = await cases.report(user_id, bill_id, analyse(stored.bill, user_id), language, "web", None, note)
    demo.mark(ticket)
    return ticket


async def misread_next_bill() -> str:
    """Isnapur. Six normal months, a September reading keyed far too high, then October starts below it."""
    user_id, service = _consumer()
    keyed = make_bill(service, "Isnapur", 1, 8420, 9290, [162, 178, 189, 184, 171, 158])
    keyed_id = ingest(user_id, keyed)
    ticket = await _report(user_id, keyed_id, "en", "The reading on this bill is much higher than what my meter "
                           "shows. We have not used anything more than in other months.")
    demo.backdate(ticket, [keyed_id], 22)
    following_id = ingest(user_id, make_bill(service, "Isnapur", 0, 8592, 8763, [178, 189, 184, 171, 158, 870]))
    demo.backdate(ticket, [keyed_id, following_id], 4)
    return ticket


async def estimated_reading() -> str:
    """Kondapur. The reader did not get in (status 05), so the units were estimated; no usage table is printed,
    the system asks for three earlier bills, the consumer sends one and says they do not have the others."""
    user_id, service = _consumer()
    estimated_id = ingest(user_id, make_bill(service, "Kondapur", 1, 3262, 3502, [], status="05"))
    ticket = await _report(user_id, estimated_id, "te", "మీటర్ రీడర్ ఇంటికి రాలేదు. ఈ బిల్లు అంచనాతో వేశారు.")
    demo.backdate(ticket, [estimated_id], 24)
    earlier_id = ingest(user_id, make_bill(service, "Kondapur", 2, 3110, 3262, [148, 155, 160, 151, 149, 157]))
    demo.backdate(ticket, [estimated_id, earlier_id], 1)
    request = evidence_store.month_request(ticket)
    assert request is not None and request["status"] == "open"
    case_bills.no_bills(ticket, request["id"])
    demo.backdate(ticket, [estimated_id, earlier_id], 25)
    return ticket


async def charges_conflict() -> str:
    """Isnapur. Normal units and readings, but the fixed charge is printed for 5 kW on a 2 kW connection, so the
    charges check shows the fixed line over the tariff by the engine's own difference."""
    user_id, service = _consumer()
    bill = fixed_for_load(make_bill(service, "Isnapur", 1, 6140, 6316, [171, 168, 180, 175, 166, 172]), 5.0)
    bill_id = ingest(user_id, bill)
    ticket = await _report(user_id, bill_id, "en", "My connection is 2 kW but the fixed charges look higher than "
                           "usual. Please check the charges on this bill.")
    demo.backdate(ticket, [bill_id], 30)
    return ticket


def _staff(section_id: str) -> accounts.Account:
    """The seed's own section AE, scoped on exactly this section so routing picks it. Its password is random and
    never shown; it is switched off as soon as the decision is recorded."""
    if demo.staff(LOGIN):
        raise RuntimeError(f"{LOGIN} already exists and was not made by this seed; not touching it.")
    account = accounts.create("section_ae", LOGIN, STAFF_NAME, secrets.token_urlsafe(24), scopes=[section_id])
    accounts.audit(None, demo.STAFF_MARK, account.id, "role=section_ae, demo review seed")
    return account


async def decided(section_id: str) -> str:
    """Isnapur. August keyed too high; the AE read the meter and recorded the corrected reading. The revision is
    approved by policy and waits to be marked applied in the billing system."""
    user_id, service = _consumer()
    bill_id = ingest(user_id, make_bill(service, "Isnapur", 2, 5120, 5760, [151, 164, 170, 158, 149, 162]))
    staff = _staff(section_id)
    try:
        ticket = await _report(user_id, bill_id, "en", "This bill is about four times our usual bill. Please check "
                               "the meter reading.")
        demo.backdate(ticket, [bill_id], 70)
        first = complaints.messages(ticket)[0]["id"]
        body = DecisionBody(kind="corrected_reading", corrected_present_reading=5281, reason_code="photo_misread",
                            note="Lineman read the meter at the house and it shows 5281. The spot bill keyed 5760, "
                                 "so the present reading is corrected to the meter.",
                            evidence=[EvidenceRef(kind="bill", id=bill_id), EvidenceRef(kind="message", id=str(first))])
        await decide(ticket, body, staff)
    finally:
        accounts.update(staff.id, active=False)
        accounts.end_all_sessions(staff.id)
    demo.backdate(ticket, [bill_id], 24)
    return ticket


async def _seed(sections: dict[str, str]) -> list[tuple[str, str]]:
    # The decided case comes last: its AE is scoped on Isnapur, and while active it would take case 1 too.
    return [("misread proven by the next bill", await misread_next_bill()),
            ("estimated reading", await estimated_reading()),
            ("charges conflict", await charges_conflict()),
            ("decided, pending update", await decided(sections["Isnapur"]))]


def seed(sections: dict[str, str]) -> list[tuple[str, str]]:
    """(what it shows, ticket) for each demo review case. The caller has already removed earlier demo rows."""
    return asyncio.run(_seed(sections))
