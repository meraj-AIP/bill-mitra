"""Fixed intent set. Questions outside it get a fixed reply, never a free-form answer."""

import re
from dataclasses import dataclass
from typing import Literal

Intent = Literal[
    "why_high", "next_bill", "save", "complain", "explain_fsa", "explain_fixed",
    "explain_customer", "explain_duty", "explain_true_up", "gruha_jyothi", "due",
    "what_if", "greeting", "thanks", "power_cut", "new_connection", "help", "stop", "off_topic",
]

INTENTS: tuple[Intent, ...] = (
    "why_high", "next_bill", "save", "complain", "explain_fsa", "explain_fixed",
    "explain_customer", "explain_duty", "explain_true_up", "gruha_jyothi", "due",
    "what_if", "greeting", "thanks", "power_cut", "new_connection", "help", "stop", "off_topic",
)

# Ordered: the first matching rule wins. English, Telugu (script and romanised), Hindi, Urdu.
_RULES: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    ("stop", ("stop", "ఆపండి", "रोको", "بند کرو")),
    ("what_if", ("what if", "if i use", "వాడితే", "इस्तेमाल करूँ", "استعمال کروں")),
    ("complain", ("complain", "complaint", "wrong bill", "ఫిర్యాదు", "firyadu", "शिकायत", "شکایت")),
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


def parse_units(message: str) -> int | None:
    """A bare number, or '214 units', typed when the photo could not be read."""
    match = re.fullmatch(r"\s*(\d{1,4})\s*(?:units?|యూనిట్లు?|यूनिट|یونٹ)?\b.*", message.lower())
    if not match:
        return None
    value = int(match.group(1))
    return value if 0 <= value <= 5000 else None
