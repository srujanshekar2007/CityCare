"""CityCare FastAPI service entry point."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import settings
from app.core.duplicate_engine import MODEL_NAME, MODEL_VERSION
from app.models.model_registry import semantic_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("citycare.ml")

app = FastAPI(title="CityCare Intelligence API", version=MODEL_VERSION,
              description="Internal, explainable complaint similarity and geospatial analysis.")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                   allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"],
                   allow_headers=["Authorization", "Content-Type"])
app.include_router(router)


@app.middleware("http")
async def request_guard_and_audit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and request.method == "POST":
        try:
            if int(content_length) > 2_000_000:
                return JSONResponse(status_code=413, content={"detail": "Request body exceeds 2 MB"})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))[:80]
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error("request_failed request_id=%s path=%s error_type=%s", request_id,
                     request.url.path, type(exc).__name__)
        response = JSONResponse(status_code=500, content={"detail": "Intelligence request failed"})
    response.headers["X-Request-ID"] = request_id
    logger.info("request_complete request_id=%s path=%s status=%s duration_ms=%s",
                request_id, request.url.path, response.status_code,
                int((time.monotonic() - started) * 1000))
    return response


@app.get("/health")
def health():
    return {"status": "ok", "service": "citycare-intelligence", "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION, "semantic_model": semantic_status(load=False),
            "internal_auth_configured": bool(settings.service_token)}
