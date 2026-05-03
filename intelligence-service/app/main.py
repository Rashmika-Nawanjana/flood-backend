from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="Flood Intelligence Service")
app.include_router(router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "flood-intelligence"}
