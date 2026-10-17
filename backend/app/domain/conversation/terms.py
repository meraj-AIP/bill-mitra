"""Every line a consumer can see on a TGSPDCL / TGNPDCL spot bill, so any "what is this?" gets a real answer.

Each term has the words people use for it, a fixed explanation in every language pack (term_<code>) and, where the
bill prints it, the value from this consumer's bill. Values are read from the bill or the engine; nothing is computed
here and no model writes the answer.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.domain import meter_status
from app.domain.bill import ExtractedBill
from app.domain.conversation.facts import Facts, rs
from app.domain.conversation.lang import text

Value = Callable[[ExtractedBill, Facts, str], str | None]


@dataclass(frozen=True)
class Term:
    code: str
    keywords: tuple[str, ...]
    value: Value | None = None  # None: the bill carries no figure for it, so no "on your bill" line


def _money(amount: float | None, lang: str) -> str | None:
    return None if amount is None else text(lang, "term_money", v=rs(amount))


def _date(iso: str | None) -> str | None:
    return None if not iso else f"{iso[8:10]}-{iso[5:7]}-{iso[:4]}"


def _number(value: float | None, unit: str = "") -> str | None:
    return None if value is None else f"{value:g}{unit}"


def _item(*labels: str) -> Value:
    """A printed line found by its label, for rows that share a code with others (ACD, Interest on CD)."""
    def get(bill: ExtractedBill, _: Facts, lang: str) -> str | None:
        found = [i.amount for i in bill.line_items if any(w in i.label.lower() for w in labels)]
        return _money(sum(found), lang) if found else None
    return get


def _status(bill: ExtractedBill, _: Facts, lang: str) -> str | None:
    code = bill.present_status
    if code is None:
        return None
    kind = meter_status.kind(code)
    return text(lang, "term_status_value", code=code, why=text(lang, f"sts_{kind}"))


def _solar(bill: ExtractedBill, f: Facts, lang: str) -> str | None:
    if bill.export_units is None:
        return None
    return text(lang, "term_solar_value", imp=bill.import_units(), exp=bill.export_units, billed=f.units)


def _readings(bill: ExtractedBill, _: Facts, lang: str) -> str | None:
    if bill.previous_reading is None or bill.present_reading is None:
        return None
    return text(lang, "term_readings_value", prev=f"{bill.previous_reading:g}", pres=f"{bill.present_reading:g}")


# Order matters: the first term whose words appear wins, so specific phrases come before general ones.
TERMS: tuple[Term, ...] = (
    Term("acd", ("acd", "additional consumption deposit", "consumption deposit", "ఏసీడీ", "एसीडी", "اے سی ڈی"),
         _item("acd")),
    Term("interest_cd", ("interest on cd", "interest on sd", "interest on deposit", "deposit interest",
                         "డిపాజిట్ పై వడ్డీ", "జమ పై వడ్డీ", "जमा पर ब्याज", "ڈپازٹ پر سود"), _item("interest on cd", "interest on sd")),
    Term("interest_ed", ("interest on ed", "ed interest", "duty interest", "సుంకంపై వడ్డీ"), _item("interest on ed")),
    Term("sd", ("security deposit", "sd available", "sd amount", "deposit", "సెక్యూరిటీ డిపాజిట్", "డిపాజిట్",
                "सिक्योरिटी डिपॉजिट", "जमानत राशि", "ڈپازٹ"), lambda b, f, lang: _money(b.security_deposit, lang)),
    Term("surcharge", ("surcharge", "late fee", "late payment", "penalty", "dps", "సర్‌ఛార్జ్", "సర్చార్జ్", "ఆలస్య రుసుము",
                       "जुर्माना", "लेट फीस", "विलंब", "سرچارج", "جرمانہ"), lambda b, f, lang: _money(b.item("surcharge"), lang)),
    Term("loss_gain", ("loss/gain", "loss gain", "loss and gain", "rounding", "round off", "రౌండ్", "राउंड", "راؤنڈ"),
         _item("loss")),
    Term("adjustment", ("adjustment", "సర్దుబాటు", "समायोजन", "ایڈجسٹمنٹ"), _item("adjustment")),
    Term("total_due", ("total due", "total amount", "total payable", "how much to pay", "how much should i pay",
                       "మొత్తం ఎంత", "ఎంత కట్టాలి", "कुल देय", "कितना देना", "کل واجب", "کتنا دینا"),
         lambda b, f, lang: _money(f.total_payable, lang)),
    Term("arrears", ("arrears", "previous due", "old due", "pending amount", "credit", "బకాయి", "బాకీ", "पिछला बकाया",
                     "बकाया", "بقایا"), lambda b, f, lang: _money(b.arrears, lang)),
    Term("disc_date", ("disc date", "disconnection", "disconnect", "cut off date", "కనెక్షన్ కట్", "కట్ చేస్తారా",
                       "डिस्कनेक्शन", "कनेक्शन कट", "کنکشن کٹ"), lambda b, f, lang: _date(b.disconnection_date)),
    Term("last_paid", ("last paid", "last payment", "paid date", "చివరిగా కట్టిన", "పాత చెల్లింపు", "पिछला भुगतान",
                       "آخری ادائیگی"), lambda b, f, lang: _date(b.last_paid_date)),
    Term("md", ("recorded md", "maximum demand", "max demand", "md", "మాక్సిమం డిమాండ్", "అత్యధిక డిమాండ్",
                "अधिकतम मांग", "زیادہ سے زیادہ مانگ"), lambda b, f, lang: _number(b.recorded_md, " kW")),
    Term("pf", ("power factor", "pf", "పవర్ ఫ్యాక్టర్", "पावर फैक्टर", "پاور فیکٹر"),
         lambda b, f, lang: _number(b.power_factor)),
    Term("kvah", ("kvah", "kwh", "kva", "కేవీఏహెచ్"), None),
    Term("mf", ("mf", "multiplying factor", "multiplication factor", "గుణకం"), lambda b, f, lang: _number(b.multiplying_factor)),
    Term("phase", ("phase", "ph", "single phase", "three phase", "3 phase", "ఫేజ్", "फेज", "फ़ेज़", "فیز"),
         lambda b, f, lang: _number(b.phase)),
    Term("cf_units", ("cf units", "cf unit", "carry forward", "carried forward", "క్యారీ ఫార్వర్డ్", "कैरी फॉरवर्ड",
                      "کیری فارورڈ"), lambda b, f, lang: _number(b.carry_forward_units)),
    Term("meter_status", ("sts", "status", "door lock", "door locked", "meter stuck", "స్టేటస్", "తాళం", "స్టేటస్ కోడ్",
                          "स्टेटस", "स्थिति", "दरवाज़ा बंद", "دروازہ بند", "حالت", "اسٹیٹس"), _status),
    Term("solar", ("export", "import", "solar", "net meter", "net metering", "billed units", "సోలార్", "ఎగుమతి",
                   "దిగుమతి", "सोलर", "निर्यात", "سولر"), _solar),
    Term("load", ("contracted load", "sanctioned load", "load", "kw", "లోడ్", "लोड", "لوڈ"),
         lambda b, f, lang: _number(b.load_kw, " kW")),
    Term("readings", ("previous reading", "present reading", "meter reading", "readings", "prs", "prv", "రీడింగ్",
                      "रीडिंग", "ریڈنگ"), _readings),
    Term("days", ("billing days", "billing period", "days", "how many days", "రోజులు", "कितने दिन", "दिन", "دن"),
         lambda b, f, lang: _number(b.billing_days)),
    Term("usc", ("usc", "service number", "service no", "consumer number", "sc no", "సర్వీస్ నంబర్", "सर्विस नंबर",
                 "سروس نمبر"), lambda b, f, lang: b.masked_service_number()),
    Term("category", ("category", "cat", "lt-i", "lt-ii", "lt 1", "lt 2", "commercial", "కేటగిరీ", "కేటగిరి",
                      "श्रेणी", "कैटेगरी", "زمرہ"), lambda b, f, lang: b.category),
    Term("ero_section", ("ero", "section office", "sec", "area code", "which office", "సెక్షన్", "ఈఆర్ఓ", "सेक्शन",
                         "دفتر"), lambda b, f, lang: b.section),
    Term("str_code", ("str code", "structure code", "స్ట్రక్చర్ కోడ్"), None),
    Term("bill_amount", ("bill amount", "బిల్లు మొత్తం", "बिल राशि", "بل کی رقم"),
         lambda b, f, lang: _money(f.bill_amount, lang)),
    Term("energy", ("energy charge", "energy charges", "ఎనర్జీ ఛార్జ్", "ఎనర్జీ చార్జ్", "ऊर्जा शुल्क", "एनर्जी चार्ज",
                    "انرجی چارج"), lambda b, f, lang: _money(f.energy, lang)),
)

_ASCII_WORD = re.compile(r"^[a-z0-9 /.:-]+$")


def _hit(keyword: str, message: str) -> bool:
    # Latin words match whole words only, so "md" is not found inside "command" or "cat" inside "category".
    if _ASCII_WORD.match(keyword):
        return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", message) is not None
    return keyword in message


def match(message: str) -> Term | None:
    lowered = message.lower()
    return next((t for t in TERMS if any(_hit(k, lowered) for k in t.keywords)), None)


def answer(term: Term, bill: ExtractedBill, facts: Facts, lang: str) -> str:
    body = text(lang, f"term_{term.code}")
    if term.value is None:
        return body
    value = term.value(bill, facts, lang)
    return f"{body} {text(lang, 'term_value', value=value) if value else text(lang, 'term_not_printed')}"
