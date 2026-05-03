from fastapi import FastAPI
from app.api.routes import router as auth_router

app = FastAPI(title="Flood Auth Service")
app.include_router(auth_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "flood-auth"}
