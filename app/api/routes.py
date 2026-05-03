from fastapi import APIRouter, Depends

from app.api.routers import admin, intelligence, sensors, zones
from app.auth.keycloak import get_current_user, require_roles

router = APIRouter(prefix="/api")

# Existing service routers from dev branch
router.include_router(sensors.router)
router.include_router(zones.router)
router.include_router(intelligence.router)
router.include_router(admin.router)


@router.get("/ping", tags=["system"])
def ping() -> dict[str, str]:
    return {"message": "pong"}


@router.get("/auth/me", tags=["auth"])
def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    return {
        "authenticated": True,
        "user": current_user,
    }


@router.get("/rbac/admin-test", tags=["rbac"])
def admin_test(current_user: dict = Depends(require_roles(["admin"]))) -> dict:
    return {
        "message": "Admin access granted",
        "user": current_user,
    }


@router.get("/rbac/field-test", tags=["rbac"])
def field_test(
    current_user: dict = Depends(require_roles(["admin", "field_officer"]))
) -> dict:
    return {
        "message": "Field officer access granted",
        "user": current_user,
    }


@router.get("/rbac/citizen-test", tags=["rbac"])
def citizen_test(
    current_user: dict = Depends(require_roles(["admin", "field_officer", "citizen"]))
) -> dict:
    return {
        "message": "Citizen access granted",
        "user": current_user,
    }