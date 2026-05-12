import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.metrics import make_metrics_middleware, metrics_endpoint

app = FastAPI(title="Flood Zone Service")

_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if not _origins:
    _origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(make_metrics_middleware("flood-zone"))

app.include_router(router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "flood-zone"}


@app.get("/metrics", tags=["system"], include_in_schema=False)
def metrics():
    return metrics_endpoint()
