from fastapi import FastAPI
from app.api.routes import router
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Flood Intelligence Service")
app.include_router(router)
Instrumentator().instrument(app).expose(app)

@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "flood-intelligence"}
