"""Staff log a complaint for a consumer: a 1912 call, a walk-in at the office, or something seen in the field.

The section must be in the raiser's scope. A caller's mobile becomes the complaint's WhatsApp reply-to, so updates
reach the consumer; it is stored like any reply-to and never logged or returned. With WhatsApp not connected, the
updates go to the web chat of the consumer account on that mobile, when there is one.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints, field_validator

from app.api.complaints import ComplaintDetail, _detail
from app.api.deps import in_scope, require_perm
from app.channels.whatsapp.mapper import user_key
from app.config import get_settings
from app.core.hashing import INDIAN_MOBILE, clean_service_number, mobile_hash
from app.domain import rbac
from app.domain.complaint_types import TypeCode
from app.flows import intake
from app.store import accounts, complaints, handoffs, units
from app.store.accounts import Account
from app.store.complaints import Placement
from app.store.db import DISCOM_UNITS

router = APIRouter(prefix="/api/console/complaints", tags=["complaints"])

Creator = Annotated[Account, Depends(require_perm("complaints.create"))]
Text1000 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]
OUT_OF_SCOPE = "Pick a section in your area."


class StaffRaise(BaseModel):
    type: TypeCode
    discom: Literal["TGSPDCL", "TGNPDCL"]
    section_id: str | None = None
    service_number: str | None = None
    contact_mobile: str | None = None
    description: Text1000
    source: Literal["call_centre", "office", "field"]
    bill_id: str | None = None

    @field_validator("service_number")
    @classmethod
    def _usc(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = clean_service_number(value)
        if cleaned is None:
            raise ValueError("A service number is 5 to 16 digits.")
        return cleaned

    @field_validator("contact_mobile")
    @classmethod
    def _mobile(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        digits = value.strip().removeprefix("+91").replace(" ", "")
        if not INDIAN_MOBILE.fullmatch(digits):
            raise ValueError("Enter a 10 digit Indian mobile number.")
        return digits


def _placement(account: Account, discom: str, section_id: str | None) -> Placement:
    """The chosen section, or the DISCOM queue when none is chosen. Either way it must be in the raiser's scope."""
    if section_id is None:
        unit_id = DISCOM_UNITS[discom]
        if not in_scope(account, unit_id):
            raise HTTPException(403, OUT_OF_SCOPE)
        return Placement(section_id=None, unit_id=unit_id)
    section = units.get(section_id)
    if section is None or section.kind != "section" or section.discom != discom:
        raise HTTPException(422, "Unknown section for this DISCOM.")
    if not in_scope(account, section_id):
        raise HTTPException(403, OUT_OF_SCOPE)
    return Placement(section_id=section_id, unit_id=section_id, assigned_to=handoffs.section_holder(section_id))


def _owner(mobile: str | None, staff_id: str) -> tuple[str, str | None, str | None]:
    """Who the complaint belongs to, the channel updates go out on, and the WhatsApp reply-to. A caller with a mobile
    is the same consumer as that WhatsApp number. With WhatsApp not connected, a caller who has a Bill Mitra account
    on that mobile hears back in their web chat instead, as a WhatsApp user would on WhatsApp."""
    if not mobile:
        return f"staff:{staff_id}", None, None
    if not get_settings().whatsapp_enabled:
        found = accounts.by_login(mobile)
        if found is not None and found.active and found.role == rbac.CONSUMER:
            return found.user_id, "web", None
    reply_to = f"91{mobile}"
    return user_key(reply_to), "whatsapp", reply_to


@router.post("", response_model=ComplaintDetail, status_code=201)
async def raise_for_consumer(body: StaffRaise, account: Creator) -> ComplaintDetail:
    placement = _placement(account, body.discom, body.section_id)
    owner, channel, reply_to = _owner(body.contact_mobile, account.id)
    ticket = await intake.submit(intake.Raise(
        user_id=owner, type=body.type, discom=body.discom, description=body.description, language="te",
        channel=channel, source=body.source, service_number=body.service_number,
        bill_id=body.bill_id, reply_to=reply_to, raised_by=account.id,
        contact_hash=mobile_hash(body.contact_mobile) if body.contact_mobile else None, placement=placement))
    complaint = complaints.get(ticket)
    assert complaint is not None
    return _detail(complaint, account)
