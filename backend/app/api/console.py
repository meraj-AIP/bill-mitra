"""Department console API. Complaint routes live in app/api/complaints.py."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query

from app.api.deps import Staff
from app.store import console

router = APIRouter(prefix="/api/console", tags=["department console"])


@router.get("/summary")
async def summary(account: Staff, days: Annotated[int, Query(ge=1, le=365)] = 30,
                  discom: Literal["TGSPDCL", "TGNPDCL"] | None = None) -> dict[str, Any]:
    # An officer tied to one DISCOM only ever sees that DISCOM, whatever they ask for.
    scope = account.discom if account.role == "officer" and account.discom else discom
    return console.summary(days, scope)
