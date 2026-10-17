"""One-tap complaint, recorded in Bill Mitra with the audit finding and the bill photo for the section officer.

There is no 1912 integration yet, so the consumer is told plainly to also call 1912 with the reference."""

import re
from dataclasses import dataclass

from app.config import get_settings
from app.domain import complaint_reply
from app.domain.complaint_options import ASKS, STAFF_WORDS, Context, reply_options, type_of
from app.domain.complaint_reply import AskKind, RequestKind
from app.domain.complaint_types import BY_CODE
from app.domain.conversation import guard
from app.domain.conversation.composer import month_label
from app.domain.conversation.facts import rs
from app.domain.conversation.intents import classify
from app.flows import cases
from app.flows.analysis import Analysis, analyse
from app.flows.turn import Turn
from app.services import llm, notify
from app.store import complaints, repos
from app.store import review as review_store
from app.store.complaints import OPEN_STATUSES, Complaint

LABEL_EN = {"energy": "Energy charge", "fixed": "Fixed charge", "customer": "Customer charge",
            "duty": "Electricity duty", "fsa": "FSA", "total": "Bill amount"}


def issue_for_discom(a: Analysis) -> str:
    """The complaint text the section officer reads in the console, in English."""
    over = [line for line in a.audit.lines if line.status == "over"]
    if not over:
        return ("Consumer asked for a review. Every tariff charge matches, so please check the meter reading and "
                "the other lines on the bill.")
    parts = [f"{LABEL_EN.get(line.code, line.code)} Rs {rs(line.difference)} above TGERC tariff "
             f"(printed Rs {rs(line.printed)}, expected Rs {rs(line.expected)})" for line in over]
    return "; ".join(parts)


def _issue_for_consumer(turn: Turn, a: Analysis) -> str:
    if a.audit.overcharge:
        return turn.t("status_mismatch", over=rs(a.audit.overcharge)).replace("*", "")
    return turn.t("reason_ok")


async def preview(turn: Turn, a: Analysis) -> None:
    turn.state.awaiting = "complaint"
    service = a.bill.masked_service_number() or "-"
    month = month_label(turn.lang, a.facts.month_number, a.facts.year)
    body = turn.t("complaint_preview", service=service, month=month, issue=_issue_for_consumer(turn, a))
    await turn.buttons(body, [("complaint_send", "btn_send"), ("complaint_cancel", "btn_cancel"),
                              ("cnew", "btn_other_problem")])


async def submit(turn: Turn, a: Analysis) -> None:
    async with turn.tracer.step("Record the complaint", "channel") as step:
        issue = issue_for_discom(a)
        ticket = complaints.create(turn.state.user_id, turn.state.current_bill_id, a.bill, issue,
                                   a.audit.overcharge, turn.lang, turn.inbound.channel, turn.inbound.reply_to, issue,
                                   complaint_reply.triage(a.audit),
                                   placement=cases.place_general(a.bill.discom, a.bill.section))
        step.note(f"Reference {ticket}; bill photo and audit lines attached for the console. Not sent to 1912")
    turn.state.awaiting = None
    days = get_settings().complaint_reply_days
    await turn.say(turn.t("complaint_filed", ticket=ticket) + "\n" + turn.t("complaint_next", days=days))
    repos.log_event(turn.inbound.channel, "complaint", language=turn.lang, amount=a.audit.overcharge,
                    discom=a.bill.discom)


INFO_PREFIX = "info:"
BACKGROUND_MAX = 500
PHOTO_NOTE = "Photo from the consumer, sent after the officer asked."


@dataclass(frozen=True)
class Worded:
    text: str
    worded_by: str  # "ai" when the model reworded the option and every check passed, else "rules"


def _thread_state(ticket: str, language: str) -> tuple[set[str], set[str], bool, bool]:
    """What we asked for, what is still unanswered, and whether the consumer's last message answers us."""
    prefixes = {k: complaint_reply.request_text(k, language, ticket) for k in ASKS}
    asked: set[str] = set()
    pending: set[str] = set()
    contacted = answered = photo = False
    for m in complaints.messages(ticket):
        if m["author_kind"] == "consumer":
            pending.clear()
            answered, photo = contacted, contacted and bool(m["media_id"])
            continue
        kinds = {k for k, prefix in prefixes.items() if m["body"].startswith(prefix)}
        asked |= kinds
        pending |= kinds
        if m["author_kind"] == "officer" or kinds:  # a status line alone is not us writing to them
            contacted = True
            answered = photo = False
    for r in review_store.requests(ticket):
        asked.add(r["kind"])
        if r["status"] == "open":
            pending.add(r["kind"])
    return asked, pending, answered, photo


def options_context(complaint: Complaint) -> Context:
    """Everything the reply options are chosen from. Reads only; no model is called."""
    language = complaint.language or "te"
    found = repos.get_bill(complaint.bill_id) if complaint.bill_id else None
    a = analyse(found[0], complaint.user_id) if found else None
    asked, pending, answered, photo = _thread_state(complaint.ticket, language)
    return Context(ticket=complaint.ticket, type=type_of(complaint.type, complaint.kind), status=complaint.status,
                   language=language, facts=a.facts if a else None, audit=a.audit if a else None,
                   asked=frozenset(asked), waiting=frozenset(pending), answered=answered, sent_photo=photo)


_LONG_NUMBER = re.compile(r"\d[\d\s-]{3,}\d")
_EMAIL = re.compile(r"\S+@\S+")


def masked(said: str) -> str:
    """The consumer's words minus anything shaped like a phone, service or account number or an email: a model
    needs the gist, not their details."""
    return _EMAIL.sub("[email]", _LONG_NUMBER.sub("[number]", said))


def _background(ticket: str) -> str:
    row = complaints.row(ticket) or {}
    return masked(row.get("description") or "")[:BACKGROUND_MAX]


async def word_option(complaint: Complaint, key: str) -> Worded | None:
    """The chosen option reworded by the model, or its template when the model is off or any check fails.
    None when the option is not one this complaint is offered."""
    ctx = options_context(complaint)
    option = next((o for o in reply_options(ctx) if o.key == key), None)
    if option is None:
        return None
    worded = await llm.word_reply(option.text, ctx.language, BY_CODE[ctx.type].label, _background(complaint.ticket))
    if worded and guard.check_figures(worded, guard.numbers_in(option.text)).passed and not STAFF_WORDS.search(worded):
        return Worded(worded, "ai")
    return Worded(option.text, "rules")


def expect_answer(complaint: Complaint, kind: AskKind, account_id: str) -> None:
    """A reply that asks for something: the next photo or message is filed under the complaint, and the ask
    stays open until it comes."""
    review_store.add_request(complaint.ticket, kind, None, account_id)
    repos.set_awaiting(complaint.user_id, INFO_PREFIX + complaint.ticket)


def checked_reply(complaint: Complaint) -> str | None:
    """The rules-only draft, for bulk sends where nobody reads each reply first."""
    found = repos.get_bill(complaint.bill_id) if complaint.bill_id else None
    if not found:
        return None
    a = analyse(found[0], complaint.user_id)
    return complaint_reply.draft(a.facts, a.audit, complaint.language or "te")


async def ask(complaint: Complaint, kind: RequestKind, account_id: str, note: str | None = None) -> notify.Outcome:
    """Ask the consumer for something on their channel. Their next photo or message is filed under the complaint."""
    message = complaint_reply.request_text(kind, complaint.language or "te", complaint.ticket)
    if note:
        message += "\n" + note
    outcome = await notify.send(complaint, message)
    complaints.add_message(complaint.ticket, "officer", account_id, message, outcome.delivery, outcome.note)
    repos.set_awaiting(complaint.user_id, INFO_PREFIX + complaint.ticket)
    return outcome


async def capture_info(turn: Turn) -> bool:
    """After an officer asks for something, the consumer's next photo or message goes to that complaint."""
    awaiting = turn.state.awaiting or ""
    inbound = turn.inbound
    if not awaiting.startswith(INFO_PREFIX) or inbound.kind not in ("image", "document", "text"):
        return False
    if inbound.kind == "text" and (not inbound.text or classify(inbound.text).intent == "stop"):
        return False
    turn.state.awaiting = None
    complaint = complaints.get(awaiting.removeprefix(INFO_PREFIX))
    if complaint is None or complaint.user_id != turn.state.user_id or complaint.status not in OPEN_STATUSES:
        return False
    body = inbound.text if inbound.kind == "text" and inbound.text else PHOTO_NOTE
    media_id = inbound.media_id if inbound.kind != "text" else None
    complaints.add_message(complaint.ticket, "consumer", None, body, "stored", media_id=media_id)
    review_store.answer_requests(complaint.ticket)
    key = "review_info_received" if complaint.kind == cases.KIND else "complaint_info_received"
    await turn.say_key(key, ticket=complaint.ticket)
    return True
