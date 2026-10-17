"""A person's WhatsApp messages are handled one at a time and in arrival order across every worker, and a turn left
by a worker that died is taken over instead of blocking that person for good."""

import asyncio
import secrets

import pytest

from app.channels.whatsapp import router
from app.channels.whatsapp.mapper import IncomingWhatsApp
from app.store import wa_queue
from app.store.db import tx


def message(sender: str, text: str) -> IncomingWhatsApp:
    return IncomingWhatsApp(sender, "wamid." + secrets.token_hex(6), "text", text=text)


def sender() -> str:
    return "9199999" + str(secrets.randbelow(10**5)).zfill(5)


def test_oldest_first_and_never_two_at_once():
    who = sender()
    for text in ("one", "two", "three"):
        wa_queue.add(message(who, text))
    first = wa_queue.claim(who)
    assert first and first[1].text == "one"
    assert wa_queue.claim(who) is None  # another worker asking now gets nothing
    wa_queue.done(first[0])
    second = wa_queue.claim(who)
    assert second and second[1].text == "two"
    wa_queue.done(second[0])
    wa_queue.done(wa_queue.claim(who)[0])  # type: ignore[index]


def test_a_turn_left_by_a_dead_worker_is_taken_over():
    who = sender()
    wa_queue.add(message(who, "stuck"))
    stuck = wa_queue.claim(who)
    assert stuck and wa_queue.claim(who) is None
    with tx() as conn:
        conn.execute("UPDATE wa_turns SET claimed_at = datetime('now', '-10 minutes') WHERE id = ?", (stuck[0],))
    again = wa_queue.claim(who)
    assert again and again[0] == stuck[0]
    wa_queue.done(again[0])


def test_two_workers_draining_one_sender_never_overlap(monkeypatch: pytest.MonkeyPatch):
    who = sender()
    seen: list[str] = []
    running = 0

    async def turn(incoming: IncomingWhatsApp) -> None:
        nonlocal running
        running += 1
        assert running == 1, "two turns of one sender ran at once"
        await asyncio.sleep(0.01)
        seen.append(incoming.text or "")
        running -= 1

    monkeypatch.setattr(router, "_turn", turn)
    for text in ("a", "b", "c", "d"):
        wa_queue.add(message(who, text))

    async def both() -> None:
        await asyncio.gather(router.drain(who), router.drain(who))

    asyncio.run(both())
    assert seen == ["a", "b", "c", "d"]
