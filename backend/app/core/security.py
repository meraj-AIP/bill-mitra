"""Browser protections: refuse cross-site writes, and send the headers every page should carry."""

from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.config import get_settings

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
EXEMPT = ("/api/whatsapp/webhook",)  # signed by Meta, not sent by a browser
CSP = ("default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
       "script-src 'self'; font-src 'self' data:; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; "
       "object-src 'self'; base-uri 'self'; form-action 'self'")


def _allowed_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin is None:
        return True  # same-origin navigations and non-browser clients; the session cookie is SameSite=Lax
    allowed = {o.strip() for o in get_settings().cors_origins.split(",") if o.strip()}
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return origin in allowed or urlsplit(origin).netloc == host


async def protect(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    if request.method in UNSAFE and request.url.path.startswith("/api/") and \
            not request.url.path.startswith(EXEMPT) and not _allowed_origin(request):
        return JSONResponse({"detail": "Request from another site refused."}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", CSP)
    if get_settings().cookie_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response
