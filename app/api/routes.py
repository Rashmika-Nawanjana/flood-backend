from fastapi import APIRouter
from app.api.routers import admin, intelligence, sensors, zones

router = APIRouter(prefix="/api")

router.include_router(sensors.router)
router.include_router(zones.router)
router.include_router(intelligence.router)
router.include_router(admin.router)
