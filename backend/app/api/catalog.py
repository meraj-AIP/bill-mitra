"""Read-only endpoints: health and provider modes, tariff tables, media."""

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import AnyAccount
from app.config import get_settings
from app.domain.insights import cliffs, what_if_curve
from app.domain.tariff.engine import compute
from app.domain.tariff.tables import TARIFF_VERSIONS
from app.store import media

router = APIRouter(prefix="/api", tags=["catalog"])


class Modes(BaseModel):
    vision: str
    language_model: str
    voice: str
    listening: str
    whatsapp: str


class Health(BaseModel):
    status: str
    modes: Modes
    whatsapp_number: str | None  # public, so the website can link consumers to the chat


@router.get("/health", response_model=Health)
async def health() -> Health:
    s = get_settings()
    live = "live"
    return Health(status="ok", modes=Modes(
        vision=live if s.vision_live else "off",
        language_model=live if s.openai_api_key else "template",
        voice=live if s.tts_live else "off",
        listening=live if s.stt_live else "off",
        whatsapp="connected" if s.whatsapp_enabled else "ready, not connected",
    ), whatsapp_number=s.whatsapp_display_number or None)


@router.get("/media/{media_id}")
async def get_media(media_id: str, _: AnyAccount) -> FileResponse:
    path = media.path_for(media_id)
    if path is None:
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type=media.mime_for(media_id),
                        headers={"Cache-Control": "private, max-age=86400"})


@router.get("/tariffs")
async def tariffs() -> list[dict[str, object]]:
    out = []
    for version in TARIFF_VERSIONS:
        data = asdict(version)
        data["effective_from"] = version.effective_from.isoformat()
        data["effective_to"] = version.effective_to.isoformat() if version.effective_to else None
        if version.true_up:
            data["true_up"]["starts"] = version.true_up.starts.isoformat()
        out.append(data)
    return out


@router.get("/tariffs/calculate")
async def calculate(
    units: int = Query(ge=0, le=2000),
    month: str = Query("2026-10", pattern=r"^\d{4}-\d{2}$"),
    gruha_jyothi: bool = False,
    load_kw: float = Query(1.0, gt=0, le=20),
) -> dict[str, object]:
    """The same engine the assistant uses, exposed for the officer-facing tariff explorer."""
    bill_month = date(int(month[:4]), int(month[5:]), 1)
    comp = compute(units, bill_month, load_kw, gruha_jyothi)
    upto = max(400, ((units + 100) // 50) * 50)
    return {
        "computation": asdict(comp),
        "curve": [p.model_dump() for p in what_if_curve(bill_month, load_kw, gruha_jyothi, upto)],
        "cliffs": [c.model_dump() for c in cliffs(bill_month, load_kw, gruha_jyothi)],
    }
