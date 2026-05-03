from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> dict[str, str]:
    return {
        "access_token": "placeholder-access-token",
        "refresh_token": "placeholder-refresh-token",
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh_token() -> dict[str, str]:
    return {
        "access_token": "placeholder-access-token",
        "refresh_token": "placeholder-refresh-token",
        "token_type": "bearer",
    }


@router.post("/logout")
def logout() -> dict[str, str]:
    return {"status": "success", "message": "Logged out successfully."}


@router.get("/me")
def me() -> dict[str, str]:
    return {"user_id": "user-123", "username": "demo_user", "role": "operator"}
