from fastapi import APIRouter

from app.api.routers import location, zones

router = APIRouter()
router.include_router(zones.router)
router.include_router(location.router)
