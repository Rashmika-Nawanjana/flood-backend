from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.metrics import make_metrics_middleware, metrics_endpoint
from app.ws.live import app as live_ws_app

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(make_metrics_middleware("flood-api"))

app.include_router(api_router)
app.mount("/ws/live", live_ws_app)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "flood-backend"}


@app.get("/metrics", tags=["system"], include_in_schema=False)
def metrics():
    return metrics_endpoint()