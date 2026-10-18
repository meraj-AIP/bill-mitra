"""Photo or PDF in, explained and checked bill out."""

import hashlib
import json
import time
from typing import Literal

from app.config import get_settings
from app.domain import capture
from app.domain.bill import ExtractedBill
from app.domain.conversation import composer, guard
from app.domain.conversation.facts import rs
from app.flows import case_bills, cases, meter, misread
from app.flows.analysis import Analysis, analyse
from app.flows.turn import Turn
from app.services import charts, llm, vision
from app.services.openai_client import ProviderError
from app.store import extract_jobs, media, repos, voice_cache

LANG_NAMES = {"te": "Telugu", "en": "English", "hi": "Hindi", "ur": "Urdu"}
MIN_TREND_MONTHS = 3
Outcome = Literal["checked", "meter", "not_a_bill", "retake", "reading_off", "reading_failed"]


def outcome(reading: vision.Reading | None, report: capture.CaptureReport | None) -> Outcome:
    """One decision shared by every surface, so the chat and the dashboard never disagree about a photo."""
    if reading is None:
        return "reading_off" if not get_settings().vision_live else "reading_failed"
    kind, bill = reading.classification.document_type, reading.bill
    if kind in ("other_bill", "other") or (bill is not None and not bill.is_electricity_bill):
        return "not_a_bill"
    if bill is None:
        return "retake"
    if kind == "meter" or bill.document_type == "meter":
        return "meter" if bill.meter_reading is not None else "retake"
    return "checked" if report is not None and report.trusted else "retake"


def read_ms(started: float) -> int | None:
    """Wall time of a vision read; None when reading is off, so instant refusals do not flatter the median."""
    return round((time.perf_counter() - started) * 1000) if get_settings().vision_live else None


def log_read(channel: str, language: str, result: Outcome, reading: vision.Reading | None, ms: int | None) -> None:
    """One read event per photo, so the console can show how often the reader is trusted and how long it takes."""
    rescued = result == "checked" and reading is not None and bool(reading.reread)
    repos.log_event(channel, "read", language=language, audit_status=result, intent="reread" if rescued else None,
                    discom=reading.bill.discom if reading and reading.bill else None, ms=ms)


async def read(turn: Turn, data: bytes, mime: str) -> vision.Reading | None:
    settings = get_settings()
    async with turn.tracer.step("Read the bill", "ai") as step:
        if not settings.vision_live:
            step.skip("Bill reading is off: OPENAI_API_KEY is not set")
            return None
        try:
            reading = await vision.read_document(data, mime)
        except ProviderError as exc:
            if exc.transient and _read_failure(turn) != "fallback":
                step.skip(f"Vision provider unavailable ({exc}); the bill will be read again shortly")
                raise
            step.skip(f"Vision provider failed ({exc}); asked the consumer to type the units")
            return None
        seen, bill = reading.classification, reading.bill
        note = f"First look ({settings.openai_vision_model}, low detail): {seen.document_type}, photo {seen.quality}"
        if bill is not None:
            note += (f". Careful read: {bill.units} units, {len(bill.line_items)} charges, "
                     f"confidence {bill.confidence:.2f}")
        if reading.reread:
            note += f". Read again because a check failed: {reading.reread.lower()}"
        step.note(note)
        return reading


async def _ask_units(turn: Turn, key: str) -> None:
    turn.state.awaiting = "units"
    await turn.buttons(turn.t(key), [("type_units", "btn_type_units")])


def _gate_note(report: capture.CaptureReport) -> str:
    checks = ", ".join(f"{c.key} {c.status}" for c in report.checks)
    verdict = "trusted" if report.trusted else f"rejected: {report.problem}"
    return f"Captured {report.captured} of {report.expected} fields; checks {checks}; {verdict}"


def _read_failure(turn: Turn) -> str:
    """Only WhatsApp queues a read for later; the web chat answers in the same request, as before."""
    if turn.read_failure == "defer" and (turn.inbound.channel != "whatsapp" or not turn.inbound.media_id):
        return "fallback"
    return turn.read_failure


async def _defer(turn: Turn, mime: str, media_id: str, error: str) -> None:
    """Keep the photo and read it again shortly (app/flows/extract.py); the consumer hears this once."""
    extract_jobs.create(turn.state.user_id, "whatsapp", media_id, mime, turn.lang, turn.inbound.reply_to, error)
    await turn.say_key("reading_later")


async def handle_document(turn: Turn, data: bytes, mime: str, media_id: str | None) -> Outcome:
    async with turn.tracer.step("Receive the message", "channel") as step:
        kind = "PDF" if mime == "application/pdf" else "photo"
        step.note(f"{kind}, {len(data) // 1024} KB, via {turn.inbound.channel}")
    started = time.perf_counter()
    try:
        reading = await read(turn, data, mime)
    except ProviderError as exc:
        if turn.read_failure == "raise" or media_id is None:
            raise
        await _defer(turn, mime, media_id, str(exc))
        return "reading_failed"
    ms = read_ms(started)
    report = capture.report(reading.bill) if reading and reading.bill else None
    result = outcome(reading, report)
    log_read(turn.inbound.channel, turn.lang, result, reading, ms)
    if report is not None:
        async with turn.tracer.step("Check the reading adds up", "rules") as step:
            step.note(_gate_note(report))
    if result == "not_a_bill":
        await turn.say_key("not_a_bill")
    elif result == "meter" and reading and reading.bill:
        await meter.handle(turn, reading.bill)
    elif result in ("reading_off", "reading_failed"):
        await _ask_units(turn, "reading_off" if result == "reading_off" else "ask_units")
    elif result == "retake":
        failed = report is not None and any(c.status == "fail" and c.key in capture.BLOCKING for c in report.checks)
        await _ask_units(turn, "not_add_up" if failed else "poor_quality")
    elif reading and reading.bill:
        await handle_bill(turn, reading.bill, media_id)
    return result


def _check_note(a: Analysis) -> str:
    note = f"{a.comp.tariff_id}, {a.comp.group}: engine total Rs {rs(a.comp.net)}; audit {a.audit.status}"
    if a.audit.overcharge:
        note += f", Rs {rs(a.audit.overcharge)} above tariff"
    if a.comp.gruha_jyothi_applied:
        note += f"; Gruha Jyothi subsidy Rs {rs(a.comp.subsidy)}"
    return note


def _explanation_key(turn: Turn, a: Analysis) -> str:
    """The same consumer, language, model and bill figures give the same explanation, so it is written once."""
    raw = json.dumps([turn.state.user_id, turn.lang, get_settings().openai_text_model, a.facts.model_dump(mode="json")],
                     sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


async def _explanation(turn: Turn, a: Analysis, discom: str | None) -> str:
    template = " ".join(composer.explain(a.facts, turn.lang))
    key = _explanation_key(turn, a)

    def logged(kind: str, text: str) -> str:
        repos.log_event(turn.inbound.channel, "explain", language=turn.lang, intent=kind, discom=discom)
        return text

    async with turn.tracer.step(f"Explain in {LANG_NAMES.get(turn.lang, 'Telugu')}", "ai") as step:
        kept = voice_cache.explanation(key)
        if kept is not None:
            # Written and number checked before; the identical text also finds its voice note already made.
            step.note("Same bill as before: the checked explanation already written is reused", "rules")
            return logged("reused", kept)
        written = await llm.explain(a.facts, turn.lang)
        if written is None:
            step.note("Checked template: every figure comes from the engine (no language-model key set)", "rules")
            return logged("template", template)
        check = guard.check(written, a.facts)
        if not check.passed:
            step.note(f"Number check failed on {', '.join(check.unmatched)}; replaced with the checked template",
                      "rules")
            return logged("llm_fallback", template)
        step.note(f"Language model wrote it. Number check passed: {check.figures_checked} of "
                  f"{check.figures_checked} figures traced to the engine")
        voice_cache.remember_explanation(key, turn.state.user_id, written)
        return logged("llm_pass", written)


async def handle_bill(turn: Turn, bill: ExtractedBill, media_id: str | None, source: str = "upload") -> None:
    async with turn.tracer.step("Check against the TGERC tariff", "rules") as step:
        a = analyse(bill, turn.state.user_id)
        step.note(_check_note(a))
    bill_id = repos.save_bill(turn.state.user_id, bill, media_id, a.audit.status, a.audit.overcharge, source)
    turn.state.current_bill_id = bill_id
    turn.state.awaiting = None
    await case_bills.tell_attached(turn, case_bills.attach_upload(turn.state.user_id, bill_id, bill, media_id))
    found = misread.after_bill_saved(turn.state.user_id, bill, bill_id)
    async with turn.tracer.step("Estimate next month", "rules") as step:
        p = a.prediction
        step.note(f"{p.units_low} to {p.units_high} units, about Rs {rs(p.amount)} ({p.method})")
    spoken = await _explanation(turn, a, bill.discom)
    if not await turn.speak(spoken):
        suffix = f"\n{turn.t('voice_unavailable')}" if turn.lang == "ur" else ""
        await turn.say(spoken + suffix)
    elif turn.inbound.channel == "whatsapp":
        # The web shows a voice note's words under it; WhatsApp cannot, so the same words follow as text.
        await turn.say(spoken)
    options = ([("report_bill", "btn_report"), ("why", "btn_why"), ("next", "btn_next")]
               if a.audit.status == "mismatch" else [("why", "btn_why"), ("next", "btn_next"), ("save", "btn_save")])
    await turn.buttons(composer.summary_card(a.facts, turn.lang), options)
    await cases.offer(turn, a)
    await cases.offer_misread(turn, found, bill.discom)
    repos.log_event(turn.inbound.channel, "bill_read", language=turn.lang, audit_status=a.audit.status,
                    units=a.comp.units, amount=a.comp.net, discom=bill.discom, section=bill.section)
    if a.prediction.crosses:
        repos.log_event(turn.inbound.channel, "alert", language=turn.lang, units=a.prediction.units,
                        discom=bill.discom, section=bill.section)
    if len(a.history) >= MIN_TREND_MONTHS:
        chart = charts.trend_png(a.history, a.facts.month, a.facts.units)
        await turn.image(media.save(chart, "image/png"), turn.t("trend_caption"))
