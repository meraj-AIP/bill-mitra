"""Bill Mitra API: conversation engine, web channel, bill dashboard, WhatsApp channel, console, and the built web app."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    access,
    admin,
    alerts,
    assist,
    auth,
    bills,
    bills_by_usc,
    catalog,
    complaint_actions,
    complaint_handoff,
    complaint_raise,
    complaints,
    console,
    consumer_complaints,
    operations,
    privacy,
    proposals,
    review,
    review_decisions,
)
from app.channels import web
from app.channels.whatsapp import router as whatsapp
from app.config import get_settings
from app.core import errors, security
from app.services import http, scheduler
from app.store import accounts, demo_accounts
from app.store import privacy as retention
from app.store.db import connection, purge_mock_data, startup_lock

errors.install_logging()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s ref=%(ref)s %(message)s")
# httpx logs every outbound request at INFO: about 20 lines per WhatsApp conversation, with URLs. Failures are still
# logged by the callers, without the URL.
for noisy in ("httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Workers starting together take turns through migration and every startup write, so none meets a lock it
    # cannot wait out. The scheduler and the resumed drains run after, once this worker's turn is over.
    with startup_lock():
        connection()
        accounts.bootstrap_admin()
        demo_accounts.ensure()
        purge_mock_data()
        retention.sweep()
        whatsapp.resume()
    scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()
        await http.close_all()


app = FastAPI(title="Bill Mitra", version="0.1.0", lifespan=lifespan,
              description="Telugu-first electricity bill assistant for Telangana. WhatsApp-first, with a web dashboard.")
# Credentials need an explicit origin list, so a wildcard entry is dropped.
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")
                                                  if o.strip() not in ("", "*")],
                   allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE"],
                   allow_headers=["*"], expose_headers=["X-Request-Id"])

app.middleware("http")(security.protect)
# Last, so it is outermost: every response, even a refusal from the middleware above, carries its reference.
errors.install(app)

for router in (auth.router, privacy.router, admin.router, alerts.router, access.router, catalog.router, bills.router,
               bills_by_usc.router, complaints.router, complaint_actions.router, complaint_handoff.router,
               complaint_raise.router, assist.router, proposals.router, consumer_complaints.router, console.router, review.router,
               review_decisions.router, operations.router, web.router, whatsapp.router):
    app.include_router(router)


if settings.frontend_dist.exists():
    class HashedAssets(StaticFiles):
        """Vite names every built asset by its content hash, so a browser may keep it for a year."""

        def file_response(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            response = super().file_response(*args, **kwargs)
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return response

    app.mount("/assets", HashedAssets(directory=settings.frontend_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (settings.frontend_dist / path).resolve()
        if path and candidate.is_file() and settings.frontend_dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        # index.html names the current asset hashes, so it is always checked again; the assets themselves are not.
        return FileResponse(settings.frontend_dist / "index.html", headers={"Cache-Control": "no-cache"})
