"""Web channel. Same engine as WhatsApp; replies stream as NDJSON so the page shows each
message and each reasoning step the moment it is ready."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import ChatUser
from app.core import service
from app.core.messages import Inbound
from app.core.ratelimit import per_ip
from app.core.trace import Event
from app.core.uploads import AUDIO, DOCUMENTS, read_checked
from app.store import chat, media, repos

router = APIRouter(prefix="/api/web", tags=["web channel"])



class WebMessage(BaseModel):
    kind: Literal["text", "image", "document", "audio", "button_reply"]
    language: Literal["te", "en", "hi", "ur"] = "te"
    text: str | None = Field(default=None, max_length=2000)
    reply_id: str | None = Field(default=None, max_length=40)
    media_id: str | None = None
    mime_type: str | None = None


class Uploaded(BaseModel):
    media_id: str
    mime_type: str
    size_kb: int


@router.post("/upload", response_model=Uploaded, dependencies=[Depends(per_ip("chat-upload", 30))])
async def upload(file: UploadFile, _: ChatUser) -> Uploaded:
    data, mime = await read_checked(file, DOCUMENTS | AUDIO)
    return Uploaded(media_id=media.save(data, mime), mime_type=mime, size_kb=len(data) // 1024)


@router.post("/messages")
async def send(message: WebMessage, account: ChatUser) -> StreamingResponse:
    if message.media_id and media.path_for(message.media_id) is None:
        raise HTTPException(404, "Upload not found; please attach it again.")
    inbound = Inbound(channel="web", user_id=account.user_id, kind=message.kind, text=message.text,
                      reply_id=message.reply_id, media_id=message.media_id, mime_type=message.mime_type)
    queue: asyncio.Queue[Event | None] = asyncio.Queue()

    async def emit(event: Event) -> None:
        await queue.put(event)

    async def run() -> None:
        try:
            await service.handle(inbound, emit, language=message.language)
        finally:
            await queue.put(None)

    async def stream() -> AsyncIterator[bytes]:
        task = asyncio.create_task(run())
        while (event := await queue.get()) is not None:
            yield (event.model_dump_json(exclude_none=True) + "\n").encode()
        await task
        yield (json.dumps({"kind": "done"}) + "\n").encode()

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/history", response_model=chat.ChatPage)
async def history(account: ChatUser, before: Annotated[int | None, Query(ge=1)] = None,
                  limit: Annotated[int, Query(ge=1, le=chat.MAX_PAGE)] = 40) -> chat.ChatPage:
    return chat.page(account.user_id, before, limit)


@router.post("/reset", status_code=204)
async def reset(account: ChatUser) -> None:
    repos.forget_user(account.user_id)
