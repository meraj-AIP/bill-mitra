"""Language-model steps. The model only phrases what the engine computed; the guard checks it."""

import json
import logging

from app.config import get_settings
from app.domain.conversation.facts import Facts
from app.domain.conversation.intents import INTENTS, Intent
from app.services.openai_client import ProviderError, chat_json

log = logging.getLogger(__name__)

LANGUAGE_NAMES = {"te": "Telugu", "en": "English", "hi": "Hindi", "ur": "Urdu"}

EXPLAIN_SYSTEM = """You are Bill Mitra, a helper for Telangana electricity consumers.
Write a short spoken explanation of the consumer's bill in {language}, for a family with little schooling.
Rules:
- Use ONLY the facts given. Every number you write must appear in the facts. Never estimate or round differently.
- Write amounts as "Rs" followed by the number (in Telugu you may write రూ.). Use Western digits.
- 5 to 8 short sentences. Simple words. No headings, no lists, no emoji.
- Order: what they pay and why (the slab), Gruha Jyothi if relevant, whether the bill is correct,
  anything unusual (true-up, arrears, overcharge), one saving tip if given, next month's estimate.
- If audit_status is "mismatch", say clearly which charge is higher than the tariff and by how much.
Return JSON: {{"text": "..."}}"""

POLISH_SYSTEM = """You help a DISCOM officer in Telangana reply to a consumer's electricity bill complaint.
Rewrite the draft reply in {language} so it reads warm, polite and natural, the way a helpful section office would write.
Rules:
- Keep every fact and every number exactly as in the draft. Add no new number, date, promise or charge.
- 2 to 5 short sentences. Simple words. No greeting by name, no sign off, no emoji.
Return JSON: {{"text": "..."}}"""

CLASSIFY_SYSTEM = """Classify a consumer's message about their electricity bill into exactly one intent from this list:
{intents}
The message may be in Telugu, Hindi, Urdu, English or romanised Telugu.
Use "dispute" when the consumer says the bill or the meter reading is wrong or far too high.
Return JSON: {{"intent": "<one intent>", "units": <integer or null, only for what_if>}}"""


async def explain(facts: Facts, language: str) -> str | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    system = EXPLAIN_SYSTEM.format(language=LANGUAGE_NAMES.get(language, "Telugu"))
    payload = facts.model_dump(exclude={"rates"})
    try:
        reply = await chat_json(settings.openai_text_model, system, json.dumps(payload), temperature=0.3,
                                 max_tokens=1200)
    except ProviderError:
        return None
    value = reply.get("text")
    return value.strip() if isinstance(value, str) and value.strip() else None


async def polish_reply(draft: str, language: str) -> str | None:
    """Rewords a checked draft. The caller guards the result against the draft's own figures."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    system = POLISH_SYSTEM.format(language=LANGUAGE_NAMES.get(language, "Telugu"))
    try:
        reply = await chat_json(settings.openai_text_model, system, draft, temperature=0.3, max_tokens=600)
    except ProviderError:
        return None
    value = reply.get("text")
    return value.strip() if isinstance(value, str) and value.strip() else None


async def classify(message: str) -> tuple[Intent, int | None] | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    system = CLASSIFY_SYSTEM.format(intents=", ".join(INTENTS))
    try:
        reply = await chat_json(settings.openai_text_model, system, message[:500], max_tokens=60)
    except ProviderError:
        return None
    intent = reply.get("intent")
    if intent not in INTENTS:
        return None
    units = reply.get("units")
    return intent, units if isinstance(units, int) else None
