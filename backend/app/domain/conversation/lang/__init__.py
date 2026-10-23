"""Language packs. Each pack holds strings only; the composer decides which apply."""

from types import ModuleType
from typing import Literal

from app.domain.conversation.lang import en, hi, te, ur

Language = Literal["te", "en", "hi", "ur"]
PACKS: dict[str, ModuleType] = {"te": te, "en": en, "hi": hi, "ur": ur}
RTL = {"ur"}


def pack(language: str) -> ModuleType:
    return PACKS.get(language, te)


def text(language: str, key: str, **values: object) -> str:
    strings: dict[str, str] = pack(language).T
    template = strings.get(key) or en.T[key]
    return template.format(**values)
