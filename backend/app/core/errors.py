"""One error shape for every API response (docs/errors-contract.md section 2):

    {"detail": {"code": "snake_case_key", "message": "Safe to show as is.", "ref": "A1B2C3", ...extras}}

Every request gets a short reference, sent back as X-Request-Id and put on every log line written while it runs, so
support can find the log from what the person sees. An unhandled error becomes a 500 in the same shape and is logged
by its type and the code lines it passed through, never its message, which may carry a request's data.
"""

import logging
import re
import secrets
import time
import traceback
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.domain.conversation.lang import PACKS, text

log = logging.getLogger(__name__)
_ref: ContextVar[str] = ContextVar("request_ref", default="")
CODES = {400: "bad_request", 401: "not_signed_in", 403: "forbidden", 404: "not_found", 405: "not_allowed",
         409: "conflict", 413: "too_large", 415: "unsupported_type", 422: "invalid", 429: "rate_limited",
         500: "server_error", 502: "upstream_failed", 503: "unavailable"}
_VALUE_ERROR = re.compile(r"^(?:Value|Assertion) error, ")
# What a staff screen shows when an error carries no text written for people.
REFUSED = "That could not be done. Please check the details and try again."


class Refusal(ValueError):
    """A refusal written for the person who asked: its text is safe to show. Any other exception's text is not."""


def safe_message(exc: Exception, fallback: str) -> str:
    return str(exc) if isinstance(exc, Refusal) else fallback


def new_ref() -> str:
    return secrets.token_hex(3).upper()


def current_ref() -> str:
    return _ref.get()


def api_error(status: int, code: str, message: str, **extras: Any) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message, **extras})


def log_failure(logger: logging.Logger, what: str, exc: BaseException, ref: str) -> None:
    """The exception's type and where it happened; never its message or the values around it."""
    frames = "".join(traceback.format_tb(exc.__traceback__)[-6:])
    logger.error("%s ref=%s: %s\n%s", what, ref, type(exc).__name__, frames.rstrip())


def install_logging() -> None:
    """Every log record carries the request's reference (or '-' outside a request), for the format in main.py."""
    make = logging.getLogRecordFactory()

    def with_ref(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = make(*args, **kwargs)
        record.ref = _ref.get() or "-"
        return record

    logging.setLogRecordFactory(with_ref)


def request_language(request: Request) -> str:
    language = request.query_params.get("language", "en")
    return language if language in PACKS else "en"


def envelope(status: int, detail: Any, ref: str, language: str = "en") -> dict[str, Any]:
    if isinstance(detail, dict):
        body = {"code": CODES.get(status, "error"), "message": text(language, "err_generic"), **detail}
    else:
        body = {"code": CODES.get(status, "error"), "message": str(detail or text(language, "err_generic"))}
    return {"detail": {**body, "ref": ref}}


def respond(status: int, detail: Any, language: str = "en", headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(envelope(status, detail, current_ref(), language), status_code=status, headers=headers)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    detail = exc.detail
    if exc.status_code == 404 and detail == "Not Found":  # the router's own, for a path that does not exist
        detail = text(request_language(request), "err_not_found")
    return respond(exc.status_code, detail, request_language(request), getattr(exc, "headers", None))


async def _invalid(request: Request, exc: Exception) -> JSONResponse:
    """One readable sentence: a validator's own words when it wrote some, else a plain request to check the form."""
    assert isinstance(exc, RequestValidationError)
    language = request_language(request)
    written = [_VALUE_ERROR.sub("", str(e.get("msg", ""))) for e in exc.errors() if e.get("type") == "value_error"]
    return respond(422, {"code": "invalid", "message": written[0] if written else text(language, "err_invalid")},
                   language)


class RequestContext:
    """Plain ASGI, outside every other middleware, so it also answers what escapes them."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ref, started, status = new_ref(), time.perf_counter(), [500, False]
        token = _ref.set(ref)

        async def send_with_ref(message: Message) -> None:
            if message["type"] == "http.response.start":
                status[:] = [message["status"], True]
                MutableHeaders(scope=message).append("X-Request-Id", ref)
            await send(message)

        try:
            await self.app(scope, receive, send_with_ref)
        except Exception as exc:
            log_failure(log, "request failed", exc, ref)
            if status[1]:
                raise  # the response had begun; nothing more can be sent
            language = request_language(Request(scope))
            await respond(500, {"code": "server_error", "message": text(language, "err_server", ref=ref)},
                          language)(scope, receive, send_with_ref)
        finally:
            if status[0] >= 400:
                route = getattr(scope.get("route"), "path", "unmatched")  # the template, so no id or number is logged
                log.info("%s %s answered %s in %d ms", scope["method"], route, status[0],
                         (time.perf_counter() - started) * 1000)
            _ref.reset(token)


def install(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _invalid)
    app.add_middleware(RequestContext)
