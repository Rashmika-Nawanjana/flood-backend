from fastapi import APIRouter
from app.api.routers import intelligence

router = APIRouter()
router.include_router(intelligence.router)
