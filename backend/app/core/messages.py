"""Channel-neutral messages, shaped on the WhatsApp Cloud API so every reply is deliverable there.

Limits enforced here, not in the channels: reply buttons max 3 with 20-character titles,
list rows max 10 with 24-character titles, body text max 1024 characters for interactive messages.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

InboundKind = Literal["text", "image", "document", "audio", "button_reply"]


class Inbound(BaseModel):
    channel: Literal["web", "whatsapp"]
    user_id: str
    kind: InboundKind
    text: str | None = None
    reply_id: str | None = None
    media_id: str | None = None  # stored in our media store once received
    mime_type: str | None = None
    reply_to: str | None = None  # channel address to answer later (WhatsApp number); never logged or shown


class Button(BaseModel):
    id: str
    title: str = Field(max_length=20)


class ListRow(BaseModel):
    id: str
    title: str = Field(max_length=24)
    description: str | None = Field(default=None, max_length=72)


class TextOut(BaseModel):
    type: Literal["text"] = "text"
    body: str = Field(max_length=4096)
    language: str


class ImageOut(BaseModel):
    type: Literal["image"] = "image"
    media_id: str
    caption: str | None = Field(default=None, max_length=1024)
    language: str


class AudioOut(BaseModel):
    type: Literal["audio"] = "audio"
    media_ids: list[str]  # one or more chunks; WhatsApp sends each as a voice note
    transcript: str
    language: str
    duration_s: float | None = None


class ButtonsOut(BaseModel):
    type: Literal["buttons"] = "buttons"
    body: str = Field(max_length=1024)
    buttons: list[Button] = Field(min_length=1, max_length=3)
    language: str


class ListOut(BaseModel):
    type: Literal["list"] = "list"
    body: str = Field(max_length=1024)
    button_label: str = Field(max_length=20)
    rows: list[ListRow] = Field(min_length=1, max_length=10)
    language: str

    @field_validator("rows")
    @classmethod
    def unique_ids(cls, rows: list[ListRow]) -> list[ListRow]:
        if len({r.id for r in rows}) != len(rows):
            raise ValueError("list row ids must be unique")
        return rows


Outbound = Annotated[TextOut | ImageOut | AudioOut | ButtonsOut | ListOut, Field(discriminator="type")]
