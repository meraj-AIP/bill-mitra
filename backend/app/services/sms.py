"""One-time codes by SMS, through the provider set in SMS_API_URL and SMS_API_KEY.

Contract (any Indian SMS gateway behind a small adapter): `POST {url}` with a bearer key and
`{"to": "91XXXXXXXXXX", "sender": "...", "template_id": "...", "variables": {"code": "123456"}}`; any 2xx is sent.
The number and the code are never logged.
"""

import logging

import httpx

from app.config import get_settings
from app.core import retry

log = logging.getLogger(__name__)
TIMEOUT_S = 10.0
# The person is waiting on the sign in page, so the budget is short.
SEND = retry.Policy(attempts=2, base_s=0.5, max_s=2.0, budget_s=8.0)


async def send_code(mobile: str, code: str) -> bool:
    settings = get_settings()
    if not settings.sms_enabled:
        return False
    body = {"to": f"91{mobile}", "sender": settings.sms_sender_id, "template_id": settings.sms_template_id,
            "variables": {"code": code}}
    headers = {"Authorization": f"Bearer {settings.sms_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            async def once() -> httpx.Response:
                return (await client.post(settings.sms_api_url, json=body, headers=headers)).raise_for_status()

            await retry.call(once, "SMS code", SEND)
    except (httpx.HTTPError, *retry.TRANSPORT) as exc:
        log.warning("SMS code not sent: %s", type(exc).__name__)
        return False
    return True
