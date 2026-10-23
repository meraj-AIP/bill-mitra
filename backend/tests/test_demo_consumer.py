"""One demo consumer: every complaint and case moves to the DEMO_OTP_MOBILE account and answers in its web chat,
other consumers and their leftovers go, staff are never touched. Numbers and service numbers are synthetic."""

import secrets

from app.domain import rbac
from app.store import accounts
from app.store.db import tx
from app.tools import demo_consumer

STAFF_OWNER = "staff:caller-without-mobile"


def _mobile() -> str:
    return "60000" + f"{secrets.randbelow(10**5):05d}"


def _complaint(conn, user_id: str, bill_id: str | None = None) -> str:
    ticket = f"BM-TEST-{secrets.token_hex(3).upper()}"
    conn.execute("INSERT INTO complaints (ticket, user_id, bill_id, discom, issue, status, language, channel, reply_to) "
                 "VALUES (?, ?, ?, 'TGSPDCL', 'test', 'open', 'en', 'whatsapp', '919999999999')",
                 (ticket, user_id, bill_id))
    return ticket


def _bill(conn, user_id: str) -> str:
    bill_id = secrets.token_hex(8)
    conn.execute("INSERT INTO bills (id, user_id, service_number, extraction, source) VALUES (?, ?, '99000', '{}', 'demo')",
                 (bill_id, user_id))
    return bill_id


def _world() -> dict[str, str]:
    """An old consumer, a stranger with chat and bills, a seeded demo household and a staff-logged complaint."""
    old = accounts.create(rbac.CONSUMER, _mobile(), "Old", "test-only-passphrase")
    stranger = accounts.create(rbac.CONSUMER, _mobile(), "Stranger", "test-only-passphrase")
    staff = accounts.create("officer", f"staff.{secrets.token_hex(3)}@example.com", "Staff", "test-only-passphrase")
    household = f"demo:{secrets.token_hex(6)}"
    with tx() as conn:
        kept_bill = _bill(conn, household)
        loose_bill = _bill(conn, f"acct:{stranger.id}")
        world = {"old": old.id, "stranger": stranger.id, "staff": staff.id, "kept_bill": kept_bill,
                 "loose_bill": loose_bill, "demo_ticket": _complaint(conn, household, kept_bill),
                 "stranger_ticket": _complaint(conn, f"acct:{stranger.id}"), "staff_ticket": _complaint(conn, STAFF_OWNER)}
        conn.execute("INSERT INTO chat_messages (user_id, ts, sender, body) VALUES (?, '2026-01-01', 'user', '{}')",
                     (f"acct:{stranger.id}",))
    return world


def _one(sql: str, *args: object) -> object:
    with tx() as conn:
        row = conn.execute(sql, args).fetchone()
    return row[0] if row else None


def test_a_dry_run_changes_nothing():
    with tx() as conn:
        conn.execute("DELETE FROM accounts WHERE role = ?", (rbac.CONSUMER,))
    world, mobile = _world(), _mobile()
    summary = demo_consumer.consolidate(mobile, apply=False)
    assert summary.complaints_moved >= 1 and summary.accounts_removed == 1
    assert accounts.by_login(mobile) is None and accounts.get(world["stranger"]) is not None
    assert _one("SELECT user_id FROM complaints WHERE ticket = ?", world["demo_ticket"]).startswith("demo:")


def test_everything_lands_on_the_demo_consumer_and_staff_stay():
    with tx() as conn:
        conn.execute("DELETE FROM accounts WHERE role = ?", (rbac.CONSUMER,))
    world, mobile = _world(), _mobile()
    summary = demo_consumer.consolidate(mobile, apply=True)
    demo = accounts.by_login(mobile)
    assert demo is not None and demo.id in (world["old"], world["stranger"]) and summary.renamed_from  # history kept
    owner, gone = f"acct:{demo.id}", world["stranger"] if demo.id == world["old"] else world["old"]
    for ticket in (world["demo_ticket"], world["stranger_ticket"]):
        assert _one("SELECT user_id || '|' || channel || '|' || COALESCE(reply_to, '-') FROM complaints "
                    "WHERE ticket = ?", ticket) == f"{owner}|web|-"
    assert _one("SELECT user_id FROM complaints WHERE ticket = ?", world["staff_ticket"]) == STAFF_OWNER
    assert _one("SELECT user_id FROM bills WHERE id = ?", world["kept_bill"]) == owner
    assert accounts.get(gone) is None and accounts.get(world["staff"]) is not None
    if gone == world["stranger"]:  # the stranger's loose bill and chat go with it
        assert _one("SELECT 1 FROM bills WHERE id = ?", world["loose_bill"]) is None
        assert _one("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", f"acct:{gone}") == 0
    assert _one("SELECT COUNT(*) FROM accounts WHERE role = ?", rbac.CONSUMER) == 1
    again = demo_consumer.consolidate(mobile, apply=True)  # a second run finds nothing left to do
    assert (again.complaints_moved, again.accounts_removed, again.renamed_from) == (0, 0, None)


def test_with_no_consumer_at_all_the_demo_consumer_is_made():
    with tx() as conn:
        conn.execute("DELETE FROM accounts WHERE role = ?", (rbac.CONSUMER,))
    mobile = _mobile()
    assert demo_consumer.consolidate(mobile, apply=False).demo_account == "(would be created)"
    assert accounts.by_login(mobile) is None
    made = demo_consumer.consolidate(mobile, apply=True)
    assert accounts.by_login(mobile) is not None and made.demo_account == accounts.by_login(mobile).id
