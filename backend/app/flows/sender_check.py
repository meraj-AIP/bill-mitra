"""Is the consumer writing from the mobile the DISCOM holds for their connection? Checked once per complaint, in the
background, so nobody waits on the DISCOM. The answer is a flag for staff; nothing is refused because of it yet.

The mobile is the complaint's reply address: the WhatsApp number (Meta has proved the sender holds it), or the
number staff typed for a caller. A complaint raised on the web uses the account's mobile when the DISCOM confirmed it
at sign up (the consumer proved it with a code); otherwise it has none and is marked so.
"""

from datetime import datetime

from app.core.hashing import service_hash
from app.domain.bill import mask
from app.services import discom_bills
from app.store import account_connections, accounts
from app.store import sender_checks as store
from app.store.sender_checks import Status

BATCH = 100


def status_for(own_hash: str | None, found: list[str], source: str) -> Status:
    """`found` are the service hashes registered to the mobile."""
    if source == "none":
        return "not_checked"
    if not found:
        return "not_registered"
    if own_hash is None:
        return "registered"
    return "verified" if own_hash in found else "other_connection"


def _confirmed_mobile(user_id: str) -> str | None:
    account = accounts.get(user_id.removeprefix("acct:")) if user_id.startswith("acct:") else None
    if account is None or account.role != "consumer" or not account_connections.for_account(account.id):
        return None
    return account.login


async def check(row: dict[str, object]) -> bool:
    """One complaint. False when the DISCOM could not be asked; it is tried again later."""
    ticket, mobile = str(row["ticket"]), row["reply_to"] or _confirmed_mobile(str(row["user_id"]))
    if not mobile:
        store.save(ticket, "no_mobile", "none", [])
        return True
    try:
        result = await discom_bills.connections_for_mobile(str(mobile), str(row["user_id"]))
    except discom_bills.LookupFailed:
        store.failed(ticket)
        return False
    kept = [(c.discom, service_hash(c.service_number), mask(c.service_number) or "", c.section) for c in result.found]
    own = str(row["service_number_hash"]) if row["service_number_hash"] else None
    store.save(ticket, status_for(own, [k[1] for k in kept], result.source), result.source, kept)  # type: ignore[arg-type]
    return True


async def run_due(_now: datetime) -> int:
    done = 0
    for row in store.due(BATCH):
        done += await check(row)
    return done
