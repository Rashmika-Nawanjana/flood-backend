from fastapi import APIRouter, Depends

from app.auth.keycloak import get_current_user

router = APIRouter(prefix="/api")


@router.get("/ping", tags=["system"])
def ping() -> dict[str, str]:
    return {"message": "pong"}


@router.get("/auth/me", tags=["auth"])
def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    return {
        "authenticated": True,
        "user": current_user,
    }