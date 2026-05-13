from app.api.routers.admin import router as admin_router
from app.api.routers.location import router as location_router
from app.api.routers.users import router as users_router
from app.api.routers.webhooks import router as webhooks_router

__all__ = [
    "admin_router",
    "location_router",
    "users_router",
    "webhooks_router",
]
