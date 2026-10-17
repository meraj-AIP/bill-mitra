"""Number check: every figure in a model-written answer must trace to the engine.

If the language model writes a number that the rule engine did not produce, the
answer is rejected and the template answer is used instead.
"""

import re

from pydantic import BaseModel

from app.domain.conversation.facts import Facts

_NATIVE_DIGITS = str.maketrans("౦౧౨౩౪౫౬౭౮౯०१२३४५६७८९۰۱۲۳۴۵۶۷۸۹",
                               "012345678901234567890123456789")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_ALWAYS_ALLOWED = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 24, 30, 50, 100, 101, 200, 201, 300,
                   400, 800, 1912, 2022, 2023, 2024, 2025, 2026, 2027}


class GuardResult(BaseModel):
    passed: bool
    figures_checked: int
    unmatched: list[str]


def allowed_numbers(facts: Facts) -> set[float]:
    allowed: set[float] = {float(n) for n in _ALWAYS_ALLOWED}
    for value in facts.model_dump().values():
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            # Text never carries the sign: a credit of -545 is written "Rs 545 in your favour".
            allowed.update({round(abs(float(value)), 2), float(round(abs(value))), float(int(abs(value)))})
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (int, float)):
                    allowed.add(round(float(item), 2))
                elif isinstance(item, tuple):
                    allowed.update(round(abs(float(v)), 2) for v in item if isinstance(v, (int, float)))
        elif isinstance(value, str):
            allowed.update(float(n) for n in re.findall(r"\d+", value))
    return allowed


def numbers_in(text: str) -> set[float]:
    return {float(raw.replace(",", "").rstrip(".")) for raw in _NUMBER.findall(text.translate(_NATIVE_DIGITS))}


def check(text: str, facts: Facts, extra: set[float] | None = None) -> GuardResult:
    """extra holds figures the caller already traced to the engine, such as those in a checked template."""
    return _against(text, allowed_numbers(facts) | (extra or set()))


def check_figures(text: str, allowed: set[float]) -> GuardResult:
    """Stricter form for a staff reply option: only the option's own figures may appear, not even the small
    numbers a bill explanation is allowed, so a reworded reply cannot add a time or a count."""
    return _against(text, allowed)


def _against(text: str, allowed: set[float]) -> GuardResult:
    found = _NUMBER.findall(text.translate(_NATIVE_DIGITS))
    unmatched = []
    for raw in found:
        value = float(raw.replace(",", "").rstrip("."))
        if not any(abs(value - a) < 0.011 for a in allowed):
            unmatched.append(raw)
    return GuardResult(passed=not unmatched, figures_checked=len(found), unmatched=unmatched)
