"""Fixed intent set and the rules that read a consumer's message. Questions outside it get a fixed reply, never a
free-form answer.

The rules match whole words (keywords.py), drop a hit that is negated ("meter is not burnt", "no complaint"), and tell
a question about the bill from a report of a problem ("why is my bill high?" against "my bill is too high, please
check"). A complaint type, when one is found, wins over the bill questions.
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.domain.conversation import keywords as k

Intent = Literal[
    "why_high", "next_bill", "save", "complain", "dispute", "explain_fsa", "explain_fixed",
    "explain_customer", "explain_duty", "explain_true_up", "gruha_jyothi", "due",
    "what_if", "greeting", "thanks", "power_cut", "new_connection", "help", "stop", "off_topic", "fetch_bill",
]

INTENTS: tuple[Intent, ...] = (
    "why_high", "next_bill", "save", "complain", "dispute", "explain_fsa", "explain_fixed",
    "explain_customer", "explain_duty", "explain_true_up", "gruha_jyothi", "due",
    "what_if", "greeting", "thanks", "power_cut", "new_connection", "help", "stop", "off_topic", "fetch_bill",
)
COMPLAINT_INTENTS = {"complain", "dispute", "power_cut"}
# Complaints about the bill amount or its reading take the bill check path when a bill is in the chat.
DISPUTE_TYPES = {"high_bill", "wrong_reading"}
STOP_WORDS = k.STOP

_NEGATORS = {"not", "never", "isn't", "isnt", "wasn't", "wasnt", "didn't", "didnt", "don't", "dont", "doesn't",
             "doesnt", "hasn't", "hasnt", "haven't", "havent", "aren't", "arent"}
_CLAUSE_END = re.compile(r"[,.;!?]|\b(?:but|and|though|although|however)\b")

# Each type is found when every pattern of any one of its clauses matches. Order matters: the first type found wins,
# so the specific (a burnt meter, a payment not shown) come before the general (no power, a high bill).
_TYPES: tuple[tuple[str, tuple[tuple[re.Pattern[str], ...], ...]], ...] = (
    ("meter_burnt", ((k.METER, k.BURN),)),
    ("payment_not_updated", ((k.PAID, k.NOT_SHOWN), (k.PAID, k.PAY_APP), (k.PAY_APP, k.NOT_SHOWN), (k.DEBITED,))),
    ("wrong_category", ((k.CATEGORY, k.CATEGORY_WRONG),)),
    ("arrears_dispute", ((k.ARREARS, k.ARREARS_WRONG),)),
    ("estimated_bill", ((k.ESTIMATED,),)),
    ("wrong_reading", ((k.READING, k.READING_WRONG),)),
    ("bill_not_received", ((k.BILL_NOT_RECEIVED,),)),
    ("voltage_fluctuation", ((k.VOLTAGE,),)),
    ("supply_other", ((k.FREQUENT, k.CUTS), (k.INTERMITTENT,), (k.PHASE,))),
    ("power_outage", ((k.OUTAGE,), (k.CUTS,))),
    ("meter_issue", ((k.METER, k.METER_FAULT),)),
)

# Words that point at some complaint type even when no type rule fires: "I have a complaint about the meter".
_EVIDENCE = (k.METER, k.BURN, k.PAID, k.PAY_APP, k.DEBITED, k.CATEGORY, k.ARREARS, k.ESTIMATED, k.READING,
             k.BILL_NOT_RECEIVED, k.VOLTAGE, k.FREQUENT, k.CUTS, k.INTERMITTENT, k.PHASE, k.OUTAGE, k.HIGH)

_UNITS = re.compile(r"(\d{1,4})\s*(?:units?|యూనిట్|यूनिट|یونٹ)?", re.IGNORECASE)


@dataclass(frozen=True)
class Classified:
    intent: Intent
    units: int | None = None
    complaint_type: str | None = None
    matched: bool = True  # False when no rule matched: the rules are silent
    negated: bool = False  # the consumer said this is not a complaint
    evidence: bool = False  # a generic complaint whose words still point at some type

    @property
    def label(self) -> str:
        """One name for what the message is: the complaint type when there is one, else the intent."""
        return self.complaint_type or self.intent


def _negated(text: str, start: int) -> bool:
    """A negation in the three words before a hit, in the same clause ("meter is not burnt"), or a "no" right before
    it ("no power cut today")."""
    words = _CLAUSE_END.split(text[:start])[-1].split()
    return any(word in _NEGATORS for word in words[-3:]) or words[-1:] == ["no"]


def hit(pattern: re.Pattern[str], text: str) -> bool:
    return any(not _negated(text, m.start()) for m in pattern.finditer(text))


def _is_question(text: str) -> bool:
    return "?" in text or hit(k.QUESTION, text)


def _complaint_type(text: str) -> str | None:
    for code, clauses in _TYPES:
        if any(all(hit(p, text) for p in clause) for clause in clauses):
            return code
    if not hit(k.HIGH, text):
        return None
    # "Why is my bill so high?" asks for the explanation; "too high, please check" asks for a check.
    if hit(k.REPORT, text) or (not _is_question(text) and hit(k.HIGH_STRONG, text)):
        return "high_bill"
    return None


def classify(message: str) -> Classified:
    text = k.normalise(message)
    if text.strip(" .!") in STOP_WORDS:
        return Classified("stop")
    if hit(k.WHAT_IF, text):
        found = _UNITS.search(text)
        return Classified("what_if", int(found.group(1)) if found else None)
    negated = bool(k.NEG_COMPLAINT.search(text))
    if not negated:
        code = _complaint_type(text)
        if code:
            return Classified("dispute" if code in DISPUTE_TYPES else "complain", complaint_type=code)
        if hit(k.COMPLAINT, text):
            return Classified("complain", evidence=any(hit(p, text) for p in _EVIDENCE))
        if hit(k.FETCH_BILL, text):
            return Classified("fetch_bill")
    for intent, pattern in k.EXPLAIN:
        if hit(pattern, text):
            return Classified(intent, negated=negated)  # type: ignore[arg-type]
    return Classified("off_topic", matched=False, negated=negated)


# A reply to the request for earlier bills saying the consumer does not have them. Checked only while one is open.
_NO_BILLS = ("don't have", "dont have", "do not have", "no bills", "not available", "lost them", "నా దగ్గర లేవు",
             "బిల్లులు లేవు", "దగ్గర లేవు", "daggara levu", "bills levu", "मेरे पास नहीं", "पास नहीं है", "पास नहीं हैं",
             "बिल नहीं हैं", "میرے پاس نہیں", "پاس نہیں ہیں", "پاس نہیں ہے", "بل نہیں ہیں")
_NO_BILLS_EXACT = {"no", "none", "లేవు", "లేదు", "levu", "ledu", "नहीं", "नहीं हैं", "نہیں", "نہیں ہیں"}


def says_no_bills(message: str) -> bool:
    lowered = message.lower().strip().strip(" .!।۔")
    return lowered in _NO_BILLS_EXACT or any(p in lowered for p in _NO_BILLS)


def parse_units(message: str) -> int | None:
    """A bare number, or '214 units', typed when the photo could not be read."""
    match = re.fullmatch(r"\s*(\d{1,4})\s*(?:units?|యూనిట్లు?|यूनिट|یونٹ)?\b.*", message.lower())
    if not match:
        return None
    value = int(match.group(1))
    return value if 0 <= value <= 5000 else None
