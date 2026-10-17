"""AI help for staff on a complaint (docs/assist-contract.md section 2), one shared brief per complaint state.

The rules build the facts and every fallback. The model may only pick from the actions the rules offer and write
short lines; anything it writes with a number the facts do not hold is dropped, and so is a consumer question that
names staff. The consumer's words reach it masked and marked as untrusted data. Figures are never computed here: they
come from the engine through the facts.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel

from app.domain.complaint_options import ASKS, STAFF_WORDS, Context, allowed_asks, ask_options, reply_options
from app.domain.complaint_types import BY_CODE
from app.domain.conversation import guard
from app.domain.conversation.facts import rs
from app.domain.conversation.lang import text
from app.flows import handoff
from app.flows.complaint import PHOTO_NOTE, masked, options_context
from app.services import llm
from app.store import assist_cache, complaints, handoffs
from app.store.accounts import Account
from app.store.complaints import OPEN_STATUSES, Complaint

ActionKind = Literal["reply_option", "request", "status", "assign"]
MAX_QUESTIONS, MAX_MISSING = 3, 4
SUMMARY_MAX, LINE_MAX, QUESTION_MAX = 600, 200, 300
WORDS_MAX, RECENT = 500, 3
RULE_WHY = "The usual first question for this type of complaint."


class Question(BaseModel):
    text: str  # the consumer's language, ready to send as a request of kind "note"
    why: str


class NextAction(BaseModel):
    kind: ActionKind
    key: str
    why: str
    account_id: str | None = None  # for "assign": the section's AE when the viewer may hand to them, else None


class ComplaintAssist(BaseModel):
    summary: str
    missing: list[str]
    questions: list[Question]
    next_action: NextAction | None
    worded_by: Literal["ai", "rules"]


def consumer_words(ticket: str, description: str | None) -> list[str]:
    """What the consumer wrote: the description and their last few messages, masked and cut short."""
    said = [m["body"] for m in complaints.messages(ticket) if m["author_kind"] == "consumer"
            and m["body"] != PHOTO_NOTE][-RECENT:]
    words = [w for w in [description or "", *said] if w.strip()]
    return [masked(w)[:WORDS_MAX] for w in dict.fromkeys(words)]


def figures(facts: dict[str, Any]) -> set[float]:
    """Every number the facts hold, and nothing else: the guard's whole allow list for model text."""
    return guard.numbers_in(json.dumps(facts, ensure_ascii=False))


def line(value: object, allowed: set[float], limit: int = LINE_MAX) -> str | None:
    """A model line kept only when it is text, short enough and holds no number the facts do not."""
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        return None
    return value.strip() if guard.check_figures(value, allowed).passed else None


def questions(raw: object, allowed: set[float]) -> list[Question]:
    """Model questions that pass every check: no unknown figure, no staff word, short. The rest are dropped."""
    out: list[Question] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        asked, why = line(item.get("text"), allowed, QUESTION_MAX), line(item.get("why"), allowed)
        if asked and why and not STAFF_WORDS.search(asked):
            out.append(Question(text=asked, why=why))
    return out[:MAX_QUESTIONS]


def lines(raw: object, allowed: set[float], most: int) -> list[str]:
    kept = [line(v, allowed) for v in raw] if isinstance(raw, list) else []
    return [v for v in kept if v][:most]


def _allowed(ctx: Context, account: Account | None, complaint: Complaint) -> dict[str, dict[str, str]]:
    """kind: {key: why}. Replies and requests are exactly what complaint_options offers right now."""
    out: dict[str, dict[str, str]] = {"reply_option": {o.key: o.why for o in reply_options(ctx)},
                                      "request": {o.kind: o.why for o in ask_options(ctx)}}
    if ctx.status in OPEN_STATUSES:
        moves = [s for s in ("In progress", "Resolved", "Rejected") if s != ctx.status]
        out["status"] = {s: f"Move the complaint to {s}." for s in moves}
    # The shared brief (no viewer) may suggest a hand-over on any open complaint; each reader's own rights decide later.
    if (handoff.targets(account, complaint) if account else complaint.kind == "general" and ctx.status in OPEN_STATUSES):
        out["assign"] = {"hand_over": "Someone else in this area should take it."}
    return {kind: keys for kind, keys in out.items() if keys}


def _facts(ctx: Context, row: dict[str, Any]) -> dict[str, Any]:
    """The complaint as the rules see it. No name, service number or phone: the ticket is the only identifier."""
    facts: dict[str, Any] = {
        "ticket": ctx.ticket, "type": BY_CODE[ctx.type].label, "status": ctx.status, "priority": row["priority"],
        "days_open": row["days_open"], "waiting_on": row["waiting_on"], "asked_for": sorted(ctx.asked),
        "still_waiting_for": sorted(ctx.waiting), "consumer_answered_last": ctx.answered,
        "consumer_sent_photo": ctx.sent_photo, "bill_check": ctx.triage}
    if ctx.facts and ctx.audit:
        facts["bill"] = {"month": ctx.facts.month, "units": ctx.facts.units, "bill_amount": ctx.facts.bill_amount,
                         "audit_status": ctx.facts.audit_status, "above_tariff": ctx.facts.overcharge}
    return facts


def _rules_summary(ctx: Context, row: dict[str, Any]) -> str:
    head = f"{BY_CODE[ctx.type].label} complaint, {ctx.status.lower()}, open {row['days_open']} days."
    bill = ""
    if ctx.facts and ctx.audit:
        found = (f"Rs {rs(ctx.facts.overcharge)} above the TGERC tariff" if ctx.facts.overcharge
                 else "every checked charge within the TGERC tariff")
        bill = f" Bill for {ctx.facts.month}: {ctx.facts.units} units, Rs {rs(ctx.facts.bill_amount)}, {found}."
    if ctx.waiting:
        now = f" Waiting for the consumer to send: {', '.join(ASKS[k][0].lower() for k in sorted(ctx.waiting))}."
    elif ctx.answered:
        now = " The consumer answered our last message; reply next."
    else:
        now = " Nothing is waiting on the consumer."
    return head + bill + now


def _rules_missing(ctx: Context) -> list[str]:
    missing = [f"{ASKS[k][0]}: not asked yet" for k in allowed_asks(ctx) if k not in ctx.asked]
    missing += [f"{ASKS[k][0]}: asked, no answer yet" for k in sorted(ctx.waiting) if k in ASKS]
    return missing[:MAX_MISSING]


def rule_questions(ctx: Context) -> list[Question]:
    if ctx.status not in OPEN_STATUSES or ctx.waiting:
        return []
    return [Question(text=text(ctx.language, f"assist_q_{ctx.type}"), why=RULE_WHY)]


def suggested_holder(account: Account, complaint: Complaint) -> str | None:
    """The section's AE, offered only when this viewer may hand the complaint to them."""
    ae = handoffs.section_holder(complaint.section_id) if complaint.section_id else None
    return ae if ae and any(p["id"] == ae for p in handoff.targets(account, complaint)) else None


def _with_holder(action: NextAction | None, account: Account | None, complaint: Complaint) -> NextAction | None:
    if action is None or action.kind != "assign" or account is None:
        return action
    return action.model_copy(update={"account_id": suggested_holder(account, complaint)})


def _rules_next(allowed: dict[str, dict[str, str]]) -> NextAction | None:
    """The best fitting reply: complaint_options lists it first."""
    best = next(iter(allowed.get("reply_option", {}).items()), None)
    return NextAction(kind="reply_option", key=best[0], why=best[1]) if best else None


def _next(raw: object, allowed: dict[str, dict[str, str]], figures_ok: set[float]) -> NextAction | None:
    """The model's pick when its kind and key are on offer, else None."""
    if not isinstance(raw, dict):
        return None
    kind, key = raw.get("kind"), raw.get("key")
    if not isinstance(kind, str) or not isinstance(key, str) or key not in allowed.get(kind, {}):
        return None
    return NextAction.model_validate({"kind": kind, "key": key,
                                      "why": line(raw.get("why"), figures_ok) or allowed[kind][key]})


async def for_complaint(account: Account | None, complaint: Complaint) -> ComplaintAssist:
    ctx = options_context(complaint)
    row = complaints.row(complaint.ticket) or {}
    facts, allowed = _facts(ctx, row), _allowed(ctx, account, complaint)
    rules = ComplaintAssist(summary=_rules_summary(ctx, row), missing=_rules_missing(ctx), questions=rule_questions(ctx),
                            next_action=_with_holder(_rules_next(allowed), account, complaint), worded_by="rules")
    reply = await llm.assist("complaint", ctx.language, {
        "facts": facts, "allowed": allowed, "consumer_words": consumer_words(ctx.ticket, row.get("description"))})
    summary = line(reply.get("summary"), figures(facts), SUMMARY_MAX) if reply else None
    if reply is None or summary is None:
        return rules
    ok = figures(facts)
    return ComplaintAssist(summary=summary, missing=lines(reply.get("missing"), ok, MAX_MISSING) or rules.missing,
                           questions=questions(reply.get("questions"), ok) or rules.questions,
                           next_action=_with_holder(_next(reply.get("next_action"), allowed, ok), account, complaint)
                           or rules.next_action,
                           worded_by="ai")


class ComplaintBrief(ComplaintAssist):
    generated_at: str


_locks: dict[str, asyncio.Lock] = {}


async def once(key: str, stale: Callable[[], bool], make: Callable[[], Awaitable[bool]]) -> bool | None:
    """Runs make() only if the brief is still stale once the lock is held, so two staff opening the same complaint
    at the same moment cause one model call, not two."""
    lock = _locks.setdefault(key, asyncio.Lock())
    try:
        async with lock:
            return await make() if stale() else None
    finally:
        if not lock.locked():
            _locks.pop(key, None)


async def brief(account: Account, complaint: Complaint, refresh: bool = False) -> tuple[ComplaintBrief, bool]:
    """The complaint's shared brief, written again only when the complaint changed or someone asked for a refresh.
    Only the next step is fitted to this reader: it must be something they may do. True when a new one was written."""
    ticket = complaint.ticket

    def stale() -> bool:
        found = assist_cache.get(ticket, "complaint")
        return refresh or found is None or found["fingerprint"] != assist_cache.fingerprint(ticket)

    async def make() -> bool:
        fp = assist_cache.fingerprint(ticket)
        shared = await for_complaint(None, complaint)
        assist_cache.put(ticket, "complaint", fp, shared.model_dump())
        return True

    made = bool(await once(f"complaint:{ticket}", stale, make)) if stale() else False
    stored = assist_cache.get(ticket, "complaint")
    assert stored is not None
    shared = ComplaintAssist.model_validate(stored["payload"])
    allowed = _allowed(options_context(complaint), account, complaint)
    pick = shared.next_action
    mine = pick if pick and pick.key in allowed.get(pick.kind, {}) else _rules_next(allowed)
    return ComplaintBrief(**shared.model_dump(exclude={"next_action"}), next_action=_with_holder(mine, account, complaint),
                          generated_at=stored["generated_at"]), made
