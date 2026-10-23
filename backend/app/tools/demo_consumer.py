"""One demo consumer for the whole server: python -m app.tools.demo_consumer [--apply]

The consumer whose mobile is DEMO_OTP_MOBILE becomes the only consumer. Every complaint and case, and the bills they
point at, move to that account and answer in its web chat (there is no WhatsApp on a demo server). Every other
consumer account goes, with its chats, drafts, codes and the bills nothing points at. Staff accounts, their chat
previews and complaints staff logged for a caller with no mobile are left alone. Without --apply it only reports.
"""

import argparse
import secrets
import sys
from dataclasses import asdict, dataclass
from typing import Any

from app.config import get_settings
from app.domain import rbac
from app.store import accounts, media
from app.store.db import tx

# Owner keys that belong to a consumer, not to staff: the seed's demo households, anonymous web chats, WhatsApp numbers.
CONSUMER_PREFIXES = ("demo:", "web:", "wa:")
GONE_WITH_THE_OWNER = ("users", "consents", "chat_messages", "chat_drafts", "usc_codes", "extract_jobs",
                       "explain_cache", "pending_reads", "voice_jobs")
GONE_WITH_THE_ACCOUNT = ("sessions", "account_connections", "alerts", "alert_reads", "account_scopes")


@dataclass
class Summary:
    demo_account: str
    renamed_from: str | None
    complaints_moved: int
    bills_moved: int
    bills_removed: int
    accounts_removed: int
    owners_cleared: int


def _marks(values: list[str]) -> str:
    return ",".join("?" * len(values))


def _target(conn: Any, mobile: str) -> tuple[str, str | None]:
    """The demo consumer's id. An existing consumer account is renamed to the demo mobile, so its history stays."""
    login = accounts.normalise_login(mobile)
    found = conn.execute("SELECT id FROM accounts WHERE login = ?", (login,)).fetchone()
    if found:
        return found[0], None
    old = conn.execute("SELECT id, login FROM accounts WHERE role = ? ORDER BY created_at, id LIMIT 1",
                       (rbac.CONSUMER,)).fetchone()
    if old:
        conn.execute("UPDATE accounts SET login = ?, name = 'Consumer', active = 1 WHERE id = ?", (login, old[0]))
        return old[0], old[1]
    return "", None


def _others(conn: Any, keep: str) -> tuple[list[str], list[str]]:
    """Consumer account ids to remove, and every consumer-side owner key that is not the demo consumer."""
    ids = [r[0] for r in conn.execute("SELECT id FROM accounts WHERE role = ? AND id <> ?", (rbac.CONSUMER, keep))]
    owners = {f"acct:{i}" for i in ids}
    for table in ("complaints", "bills", "users", "chat_messages"):
        for (owner,) in conn.execute(f"SELECT DISTINCT user_id FROM {table}"):  # noqa: S608 (fixed table names)
            if owner and owner.startswith(CONSUMER_PREFIXES):
                owners.add(owner)
    return ids, sorted(owners)


def _move(conn: Any, owners: list[str], to: str) -> tuple[int, int, int, list[str]]:
    """Complaints and the bills a complaint or case points at move; every other bill of these owners goes."""
    if not owners:
        return 0, 0, 0, []
    m = _marks(owners)
    complaints = conn.execute(f"UPDATE complaints SET user_id = ?, channel = 'web', reply_to = NULL "  # noqa: S608
                              f"WHERE user_id IN ({m})", (to, *owners)).rowcount
    kept = ("(id IN (SELECT bill_id FROM complaints WHERE bill_id IS NOT NULL) OR "
            "id IN (SELECT bill_id FROM case_bills))")
    bills = conn.execute(f"UPDATE bills SET user_id = ? WHERE user_id IN ({m}) AND {kept}",  # noqa: S608
                         (to, *owners)).rowcount
    media_ids = [r[0] for r in conn.execute(f"SELECT media_id FROM bills WHERE user_id IN ({m}) "  # noqa: S608
                                            "AND media_id IS NOT NULL", owners)]
    removed = conn.execute(f"DELETE FROM bills WHERE user_id IN ({m})", owners).rowcount  # noqa: S608
    for table in GONE_WITH_THE_OWNER:
        conn.execute(f"DELETE FROM {table} WHERE user_id IN ({m})", owners)  # noqa: S608 (fixed table names)
    conn.execute(f"DELETE FROM outbox WHERE recipient IN ({m})", owners)  # noqa: S608
    return complaints, bills, removed, media_ids


def _adopt_staff_trials(conn: Any, to: str) -> tuple[int, int]:
    """A staff account that tried the assistant as a consumer raised real consumer complaints. Those, and the bills
    they point at, belong to the demo consumer; the staff account's own chat stays with it."""
    trials = "SELECT ticket FROM complaints WHERE source = 'consumer_chat' AND user_id LIKE 'acct:%' AND user_id <> ?"
    bills = conn.execute(f"UPDATE bills SET user_id = ? WHERE id IN (SELECT bill_id FROM complaints WHERE ticket IN "
                         f"({trials}))", (to, to)).rowcount
    complaints = conn.execute(f"UPDATE complaints SET user_id = ?, channel = 'web', reply_to = NULL "
                              f"WHERE ticket IN ({trials})", (to, to)).rowcount
    # the demo consumer's own complaints answer in its web chat too, or staff replies would wait for a WhatsApp send
    conn.execute("UPDATE complaints SET channel = 'web', reply_to = NULL WHERE user_id = ? AND channel <> 'web'", (to,))
    return complaints, bills


def _drop_accounts(conn: Any, ids: list[str]) -> int:
    if not ids:
        return 0
    m = _marks(ids)
    for table in GONE_WITH_THE_ACCOUNT:
        conn.execute(f"DELETE FROM {table} WHERE account_id IN ({m})", ids)  # noqa: S608 (fixed table names)
    return conn.execute(f"DELETE FROM accounts WHERE id IN ({m})", ids).rowcount  # noqa: S608


class _DryRun(Exception):
    """Raised inside the transaction so both SQLite and Postgres roll the counted changes back."""

    def __init__(self, summary: Summary) -> None:
        super().__init__("dry run")
        self.summary = summary


def consolidate(mobile: str, apply: bool) -> Summary:
    """One transaction: everything happens, or nothing does. Without apply it is rolled back after counting."""
    if apply and accounts.by_login(mobile) is None and not _any_consumer():
        accounts.create(rbac.CONSUMER, mobile, "Consumer", secrets.token_urlsafe(24),
                        consent_version=get_settings().privacy_notice_version)
    try:
        with tx() as conn:
            target, renamed = _target(conn, mobile)
            if not target:
                raise _DryRun(Summary("(would be created)", None, 0, 0, 0, 0, 0))
            ids, owners = _others(conn, target)
            complaints, bills, removed, media_ids = _move(conn, owners, f"acct:{target}")
            dropped = _drop_accounts(conn, ids)
            trial_complaints, trial_bills = _adopt_staff_trials(conn, f"acct:{target}")
            complaints, bills = complaints + trial_complaints, bills + trial_bills
            summary = Summary(target, renamed, complaints, bills, removed, dropped, len(owners))
            if not apply:
                raise _DryRun(summary)
            conn.execute("INSERT INTO audit_log (actor_id, action, target, detail) VALUES (NULL, ?, ?, ?)",
                         ("demo.consolidate", target, f"{complaints} complaints and {bills} bills moved, "
                          f"{removed} bills and {dropped} accounts removed"))
    except _DryRun as dry:
        return dry.summary
    media.discard_unreferenced(media_ids)
    return summary


def _any_consumer() -> bool:
    with tx() as conn:
        return conn.execute("SELECT 1 FROM accounts WHERE role = ?", (rbac.CONSUMER,)).fetchone() is not None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="make the change; without it, only report")
    args = parser.parse_args(argv)
    mobile = get_settings().demo_otp_mobile
    if not mobile:
        print("Set DEMO_OTP_MOBILE (and DEMO_OTP_CODE) first: that number becomes the demo consumer.")
        return 2
    summary = consolidate(mobile, args.apply)
    print(("Applied: " if args.apply else "Dry run, nothing changed: ") + str(asdict(summary)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
