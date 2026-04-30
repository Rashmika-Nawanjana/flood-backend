from fastapi import FastAPI

from app.api.routes import router as api_router
from app.core.config import settings
from app.ws.live import app as live_ws_app

app = FastAPI(title=settings.app_name)

app.include_router(api_router)
app.mount("/ws/live", live_ws_app)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "flood-backend"}
