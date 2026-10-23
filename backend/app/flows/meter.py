"""Mid-month meter photo: where the household stands before the bill arrives."""

from datetime import date

from app.domain.bill import ExtractedBill, real_date
from app.domain.conversation.facts import rs
from app.domain.tariff.engine import compute, has_tariff
from app.flows.analysis import gruha_jyothi_eligible
from app.flows.turn import Turn
from app.store import pending_reads, repos


async def handle(turn: Turn, reading_doc: ExtractedBill, today: date | None = None) -> None:
    if reading_doc.meter_reading is None:
        await turn.say_key("meter_unreadable")
        return
    last = repos.get_bill(turn.state.current_bill_id) if turn.state.current_bill_id else None
    if last is None or last[0].present_reading is None:
        # Kept, so the projection follows as soon as the bill arrives (flows/bill.handle_bill), without a new photo.
        pending_reads.put(turn.state.user_id, "meter", reading_doc.meter_reading)
        await turn.say_key("meter_kept", reading=round(reading_doc.meter_reading))
        return
    bill = last[0]
    today = today or date.today()
    # bill_date is kept as printed, so it is parsed only when it is a real calendar date.
    since = date.fromisoformat(bill.bill_date) if real_date(bill.bill_date) else bill.month_date()
    days = max((today - since).days, 1)
    used = max(round(reading_doc.meter_reading - bill.present_reading), 0)
    async with turn.tracer.step("Project the month end", "rules") as step:
        projected = round(used / days * 30)
        eligible = gruha_jyothi_eligible(bill)
        month = today.replace(day=1)
        category = bill.tariff_category() if has_tariff(month, bill.tariff_category()) else "domestic"
        amount = compute(projected, month, bill.load_kw or 1.0, eligible, category=category).net
        step.note(f"{used} units in {days} days; month end about {projected} units, Rs {rs(amount)}")
    message = turn.t("meter_projection", reading=round(reading_doc.meter_reading), used=used, days=days,
                     proj=projected, amount=rs(amount))
    if projected > 200 >= used:
        message += "\n" + turn.t("warn_gj" if eligible else "warn_cross", t=200)
    await turn.say(message)
    repos.log_event(turn.inbound.channel, "meter_read", language=turn.lang, units=projected, amount=amount)
