"""Application entry point.

Serves the API and, in production, the built Nuxt SPA from the same origin
(single port for the whole clinic: http://<server-ip>:8000).
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import FRONTEND_DIST, get_settings
from app.core.db import check_database
from app.core.errors import register_exception_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("clinic")

app = FastAPI(title="Clinique Dentaire", docs_url=None, redoc_url=None, openapi_url=None)

# Production serves the SPA from the same origin -> no CORS headers at all.
# Localhost dev origins are enabled for the Nuxt dev server only, plus any
# extra origins explicitly configured via CLINIC_CORS_EXTRA_ORIGINS.
_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:52490",
]
_cors_origins += [o.strip() for o in get_settings().cors_extra_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

from app.agenda.api import router as agenda_router  # noqa: E402
from app.backup.api import router as backup_router  # noqa: E402
from app.clinical.api import router as clinical_router  # noqa: E402
from app.core.auth_api import router as auth_router  # noqa: E402
from app.devis.api import router as devis_router  # noqa: E402
from app.documents.api import router as documents_router  # noqa: E402
from app.dsp.api import router as dsp_router  # noqa: E402
from app.labs.api import router as labs_router  # noqa: E402
from app.patients.api import router as patients_router  # noqa: E402
from app.payments.api import router as payments_router  # noqa: E402
from app.settings.api import router as settings_router  # noqa: E402
from app.sterilization.api import router as sterilization_router  # noqa: E402
from app.stock.api import router as stock_router  # noqa: E402

app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(agenda_router)
app.include_router(clinical_router)
app.include_router(payments_router)
app.include_router(documents_router)
app.include_router(dsp_router)
app.include_router(devis_router)
app.include_router(sterilization_router)
app.include_router(labs_router)
app.include_router(stock_router)
app.include_router(settings_router)
app.include_router(backup_router)


@app.get("/api/health")
def health():
    return {"ok": True, "database": check_database()}


# --------------------------------------------------------------------------- #
# SPA serving (production). The Nuxt build output lives in frontend/.output/public
# --------------------------------------------------------------------------- #

_dist = FRONTEND_DIST
if _dist.is_dir():
    app.mount("/_assets", StaticFiles(directory=_dist / "_assets"), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = (_dist / full_path).resolve()
        if full_path and candidate.is_file() and str(candidate).startswith(str(_dist.resolve())):
            return FileResponse(candidate)
        # SPA fallback: unknown routes render the app shell.
        index = _dist / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse({"error": {"code": "not_found", "message_key": "errors.not_found"}}, status_code=404)

    logger.info("Serving frontend from %s", _dist)
else:
    logger.warning("Frontend build not found at %s (API-only mode)", _dist)

# --------------------------------------------------------------------------- #
# Startup: schema bootstrap + daily backup scheduler
# --------------------------------------------------------------------------- #


@app.on_event("startup")
def startup() -> None:
    from app.core.db import get_session_factory

    db = get_session_factory()()
    try:
        _ensure_schema(db)
    finally:
        db.close()

    from app.backup.service import BackupScheduler

    BackupScheduler().start()


def _ensure_schema(db) -> None:
    """Create/upgrade schema via Alembic on startup (idempotent)."""
    from alembic import command
    from alembic.config import Config


    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "migrations"))
    cfg.attributes["configure_logger"] = False
    try:
        command.upgrade(cfg, "head")
        logger.info("Database schema is up to date")
    except Exception:
        logger.exception("Migration failed")
        raise
