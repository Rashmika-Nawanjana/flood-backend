from fastapi import APIRouter
from app.api.routers import zones

router = APIRouter()
router.include_router(zones.router)
