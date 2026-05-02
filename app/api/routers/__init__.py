from app.api.routers.admin import router as admin_router
from app.api.routers.intelligence import router as intelligence_router
from app.api.routers.sensors import router as sensors_router
from app.api.routers.zones import router as zones_router

__all__ = ["sensors_router", "zones_router", "intelligence_router", "admin_router"]
