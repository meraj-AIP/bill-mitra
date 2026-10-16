"""Department console API. Complaint routes live in app/api/complaints.py."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_perm
from app.store import console
from app.store.accounts import Account

router = APIRouter(prefix="/api/console", tags=["department console"])


@router.get("/summary")
async def summary(account: Annotated[Account, Depends(require_perm("console.view"))],
                  days: Annotated[int, Query(ge=1, le=365)] = 30,
                  discom: Literal["TGSPDCL", "TGNPDCL"] | None = None) -> dict[str, Any]:
    # Staff whose scopes sit in one DISCOM only ever see that DISCOM, whatever they ask for.
    scope = account.discom or discom
    return console.summary(days, scope)
