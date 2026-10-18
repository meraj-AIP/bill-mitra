"""Admin Operations: what the queues could not do on their own, with Retry and Dismiss. Every action is audited."""

from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Response

from app.api.deps import require_perm
from app.channels.whatsapp import router as whatsapp
from app.store import accounts, extract_jobs, outbox, wa_queue
from app.store import operations as store
from app.store.accounts import Account
from app.store.operations import Kind, ParkedPage

router = APIRouter(prefix="/api/admin/operations", tags=["admin"])

Operator = Annotated[Account, Depends(require_perm("audit.view", "accounts.manage"))]
ItemId = Annotated[str, Path(max_length=40, pattern=r"^[A-Za-z0-9_-]+$")]
NOT_FOUND = "No parked item with this id."


@router.get("", response_model=ParkedPage)
def parked(account: Operator, page: Annotated[int, Query(ge=1, le=1000)] = 1,
           page_size: Annotated[int, Query(ge=5, le=100)] = 20, kind: Kind | None = None,
           sort: Literal["newest", "oldest"] = "newest") -> ParkedPage:
    return store.page(account, page, page_size, kind, sort == "newest")


def _found(account: Account, kind: Kind, item_id: str) -> None:
    if (kind != "extract" and not item_id.isdigit()) or not store.visible(account, kind, item_id):
        raise HTTPException(404, NOT_FOUND)


@router.post("/{kind}/{item_id}/retry", status_code=204)
async def retry(kind: Kind, item_id: ItemId, account: Operator, tasks: BackgroundTasks) -> Response:
    _found(account, kind, item_id)
    if kind == "inbound":
        done = wa_queue.retry(int(item_id))
        sender = wa_queue.sender_of(int(item_id))
        if done and sender:
            tasks.add_task(whatsapp.drain, sender)
    elif kind == "outbound":
        done = outbox.retry(int(item_id))
    else:
        done = extract_jobs.retry(item_id)
    if not done:
        # A one-time code or a WhatsApp bill read keeps no number to send to, so it cannot go again.
        raise HTTPException(409, "This item cannot be retried. Dismiss it instead.")
    accounts.audit(account.id, "operations.retry", f"{kind}:{item_id}")
    return Response(status_code=204)


@router.post("/{kind}/{item_id}/dismiss", status_code=204)
async def dismiss(kind: Kind, item_id: ItemId, account: Operator) -> Response:
    _found(account, kind, item_id)
    if kind == "inbound":
        wa_queue.dismiss(int(item_id))
    elif kind == "outbound":
        outbox.dismiss(int(item_id))
    else:
        extract_jobs.dismiss(item_id)
    accounts.audit(account.id, "operations.dismiss", f"{kind}:{item_id}")
    return Response(status_code=204)
