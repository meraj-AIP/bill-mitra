"""Shared setup for the access and review tests: a small unit tree with unique names, and real bills.

Every bill here is a real fixture from tests/real.py. Where a test needs a situation no real bill shows, it uses a
labelled variant with the units and readings changed.
"""

import secrets
from dataclasses import dataclass

from app.domain.bill import ExtractedBill, UsagePoint
from app.domain.pricing import price
from app.store import units
from app.store.db import DISCOM_UNITS
from app.store.units import Unit
from tests.real import OCT_2025, variant

# Variant of the real October 2025 bill: the meter was read as 480 units (present 693) where the household's
# printed table shows about 138 a month. Every printed charge is as on the real bill.
USUAL_MONTHS = [UsagePoint(month=m, units=u) for m, u in
                (("2025-06", 130), ("2025-07", 138), ("2025-08", 142), ("2025-09", 135))]
def _misread(units: int, present: float) -> ExtractedBill:
    """The real October 2025 bill as it would print had its reading been misread: the tariff lines follow the wrong
    units, the surcharge, interest and rounding lines stay as printed. A labelled variant of a real bill."""
    wrong = price(OCT_2025, units, units)
    lines = [{**i.model_dump(), "amount": getattr(wrong, i.code)} if i.code in ("energy", "fixed", "customer", "duty")
             else i.model_dump() for i in OCT_2025.line_items]
    amount = round(sum(line["amount"] for line in lines), 2)
    return variant(OCT_2025, units=units, present_reading=present, usage_history=USUAL_MONTHS, line_items=lines,
                   bill_amount=amount, total_payable=round(amount + OCT_2025.arrears, 2))


# The real bill with its reading misread as 693 instead of 351: 480 units billed instead of 138.
SPIKED = _misread(480, 693.0)
# Variant of the same real bill with the same usual months, and this month's real 138 units: a normal month.
NORMAL = variant(OCT_2025, usage_history=USUAL_MONTHS)


@dataclass
class Tree:
    tag: str
    discom: str
    circle: Unit
    division: Unit
    subdivision: Unit
    ero: Unit
    section_a: Unit
    section_b: Unit


def tree(discom: str = "TGSPDCL") -> Tree:
    """circle > division > subdivision > sections A and B, with an ERO under the division billing section A."""
    tag = secrets.token_hex(3).upper()
    circle = units.create("circle", f"Circle {tag}", f"C{tag}", DISCOM_UNITS[discom])
    division = units.create("division", f"Division {tag}", f"D{tag}", circle.id)
    sub = units.create("subdivision", f"Subdivision {tag}", f"S{tag}", division.id)
    ero = units.create("ero", f"ERO {tag}", f"E{tag}", division.id)
    section_a = units.create("section", f"Section A {tag}", f"SA{tag}", sub.id, ero.id, [f"SEC A-{tag} (old)"])
    section_b = units.create("section", f"Section B {tag}", f"SB{tag}", sub.id)
    return Tree(tag, discom, circle, division, sub, ero, section_a, section_b)


def printed(bill: ExtractedBill, section: str | None, discom: str = "TGSPDCL") -> ExtractedBill:
    """The same real bill as printed by a given section office."""
    return variant(bill, section=section, discom=discom)
