from fastapi import APIRouter
from app.api.routers import sensors

router = APIRouter()
router.include_router(sensors.router)
