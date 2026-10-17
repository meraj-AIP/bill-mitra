"""Fixed intent set. Questions outside it get a fixed reply, never a free-form answer."""

import re
from dataclasses import dataclass
from typing import Literal

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

# Ordered: the first matching rule wins. English, Telugu (script and romanised), Hindi, Urdu.
_RULES: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    ("stop", ("stop", "ఆపండి", "रोको", "بند کرو")),
    ("what_if", ("what if", "if i use", "వాడితే", "इस्तेमाल करूँ", "استعمال کروں")),
    # Before complain and why_high: "wrong bill" and "too high" mean this bill should be checked, not explained.
    ("dispute", ("bill is wrong", "wrong bill", "bill wrong", "bill looks wrong", "incorrect bill", "bill is incorrect",
                 "too high", "too much bill", "reading is wrong", "wrong reading", "reading wrong",
                 "బిల్లు తప్పు", "తప్పు బిల్లు", "రీడింగ్ తప్పు", "తప్పుగా వచ్చింది", "మరీ ఎక్కువ", "bill tappu",
                 "reading tappu", "बिल गलत", "बिल ग़लत", "गलत बिल", "ग़लत बिल", "रीडिंग गलत", "रीडिंग ग़लत",
                 "गलत रीडिंग", "बहुत ज़्यादा बिल", "बिल बहुत ज़्यादा", "بل غلط", "غلط بل", "ریڈنگ غلط", "غلط ریڈنگ",
                 "بہت زیادہ بل", "بل بہت زیادہ")),
    ("complain", ("complain", "complaint", "ఫిర్యాదు", "firyadu", "शिकायत", "شکایت")),
    # Asking for the bill by service number, before the charge words so "get my bill" is not read as a question.
    ("fetch_bill", ("get my bill", "fetch my bill", "bill by usc", "bill with usc", "bill by service number",
                    "సర్వీస్ నంబర్‌తో బిల్లు", "నా బిల్లు తెప్పించ", "सर्विस नंबर से बिल", "मेरा बिल मँगा",
                    "سروس نمبر سے بل", "میرا بل منگوا")),
    ("explain_true_up", ("true-up", "true up", "trueup", "ట్రూ", "ट्रू", "ٹرو")),
    ("explain_fsa", ("fsa", "fuel", "ఇంధన", "ईंधन", "ایندھن")),
    ("explain_fixed", ("fixed", "ఫిక్స్", "फ़िक्स्ड", "फिक्स्ड", "فکسڈ")),
    ("explain_customer", ("customer charge", "కస్టమర్", "कस्टमर", "کسٹمر")),
    ("explain_duty", ("duty", "సుంకం", "शुल्क", "ڈیوٹی")),
    ("gruha_jyothi", ("gruha", "jyothi", "free units", "subsidy", "గృహ", "జ్యోతి", "गृह ज्योति", "گرہ")),
    ("next_bill", ("next month", "next bill", "predict", "వచ్చే నెల", "vache nela", "अगले महीने", "अगला", "اگلے مہینے", "اگلا")),
    ("save", ("save", "reduce", "lower", "ఆదా", "తగ్గించ", "बचत", "बचा", "کم کر", "بچت")),
    ("why_high", ("why", "high", "so much", "increase", "ఎందుకు", "enduku", "ఎక్కువ", "ekkuva", "क्यों", "ज़्यादा", "کیوں", "زیادہ")),
    ("due", ("due", "last date", "pay by", "when to pay", "చివరి తేదీ", "ఎప్పుడు కట్ట", "अंतिम तिथि", "कब तक", "آخری تاریخ")),
    ("power_cut", ("power cut", "no power", "outage", "కరెంటు పోయ", "కరెంట్ లేదు", "बिजली नहीं", "कटौती", "بجلی نہیں")),
    ("new_connection", ("new connection", "కొత్త కనెక్షన్", "नया कनेक्शन", "نیا کنکشن")),
    ("thanks", ("thank", "thanks", "ధన్యవాద", "థ్యాంక్స్", "धन्यवाद", "शुक्रिया", "شکریہ")),
    ("greeting", ("hello", "hi ", "namaste", "namaskaram", "నమస్కారం", "హలో", "नमस्ते", "सलाम", "السلام")),
    ("help", ("help", "menu", "సహాయం", "मदद", "مدد")),
)

_UNITS = re.compile(r"(\d{1,4})\s*(?:units?|యూనిట్|यूनिट|یونٹ)?", re.IGNORECASE)


@dataclass(frozen=True)
class Classified:
    intent: Intent
    units: int | None = None


def classify(message: str) -> Classified:
    lowered = f" {message.lower().strip()} "
    for intent, keywords in _RULES:
        if any(k in lowered for k in keywords):
            units = None
            if intent == "what_if":
                match = _UNITS.search(lowered)
                units = int(match.group(1)) if match else None
            return Classified(intent, units)
    return Classified("off_topic")


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
