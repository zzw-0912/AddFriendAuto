import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.client_update import router as client_update_router
from app.api.devices import router as devices_router
from app.api.feedback import router as feedback_router
from app.api.health import router as health_router
from app.api.hero_slides import router as hero_slides_router
from app.api.orders import router as orders_router
from app.api.payments import router as payments_router
from app.api.plans import router as plans_router
from app.api.profile import router as profile_router
from app.api.status import router as status_router
from app.api.tasks import router as tasks_router
from app.core.database import SessionLocal
from app.core.logging import configure_logging
from app.services.client_update_service import (
    build_upgrade_required_payload,
    ensure_client_update_config,
    is_client_update_required,
)
from app.seed import init_db


configure_logging()
logger = logging.getLogger("friendauto.main")
request_logger = logging.getLogger("friendauto.requests")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup_begin")
    init_db()
    logger.info("app_startup_complete")
    yield


app = FastAPI(title="FriendAuto API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uploads_dir = Path(os.getenv("UPLOADS_DIR", "uploads")).resolve()
uploads_dir.mkdir(parents=True, exist_ok=True)
logger.info("uploads_static_mount directory=%s exists=%s", uploads_dir, uploads_dir.exists())
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


def _skip_client_version_check(path: str, method: str) -> bool:
    if method.upper() == "OPTIONS":
        return True
    return (
        path.startswith("/admin")
        or path.startswith("/uploads")
        or path.startswith("/health")
        or path == "/client-update/config"
    )


@app.middleware("http")
async def enforce_client_version(request: Request, call_next):
    path = request.url.path
    if _skip_client_version_check(path, request.method):
        return await call_next(request)

    db = SessionLocal()
    try:
        config = ensure_client_update_config(db)
        client_version = request.headers.get("x-client-version")
        if is_client_update_required(config, client_version):
            request_logger.warning(
                "client_update_required method=%s path=%s client_version=%s latest_version=%s",
                request.method,
                path,
                client_version,
                config.latest_version,
            )
            response = JSONResponse(
                status_code=426,
                content=jsonable_encoder(build_upgrade_required_payload(config)),
            )
            response.headers["X-Required-Client-Version"] = config.latest_version
            return response
    except Exception:
        request_logger.exception("client_update_check_failed method=%s path=%s", request.method, path)
    finally:
        db.close()

    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    path = request.url.path
    method = request.method
    client = request.client.host if request.client else "-"
    should_trace = path.startswith((
        "/hero-slides",
        "/admin/hero-slides",
        "/uploads/hero-slides",
        "/client-update",
        "/admin/client-update",
        "/uploads/client-update",
    ))

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        request_logger.exception(
            "request_failed request_id=%s method=%s path=%s client=%s elapsed_ms=%.2f",
            request_id,
            method,
            path,
            client,
            elapsed_ms,
        )
        raise

    response.headers["X-Request-ID"] = request_id
    elapsed_ms = (time.perf_counter() - start) * 1000
    if response.status_code >= 500:
        request_logger.error(
            "request_error request_id=%s method=%s path=%s status=%s client=%s elapsed_ms=%.2f",
            request_id,
            method,
            path,
            response.status_code,
            client,
            elapsed_ms,
        )
    elif response.status_code >= 400:
        request_logger.warning(
            "request_warning request_id=%s method=%s path=%s status=%s client=%s elapsed_ms=%.2f",
            request_id,
            method,
            path,
            response.status_code,
            client,
            elapsed_ms,
        )
    elif should_trace:
        request_logger.info(
            "request_ok request_id=%s method=%s path=%s status=%s client=%s elapsed_ms=%.2f",
            request_id,
            method,
            path,
            response.status_code,
            client,
            elapsed_ms,
        )
    return response

app.include_router(health_router)
app.include_router(client_update_router)
app.include_router(auth_router)
app.include_router(devices_router)
app.include_router(status_router)
app.include_router(plans_router)
app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(feedback_router)
app.include_router(hero_slides_router)
app.include_router(profile_router)
app.include_router(tasks_router)
app.include_router(admin_router)
