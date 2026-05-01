from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.services import keycloak

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> dict[str, str]:
    tokens = keycloak.login(payload.username, payload.password)
    return {
        "access_token": tokens.get("access_token", ""),
        "refresh_token": tokens.get("refresh_token", ""),
        "token_type": tokens.get("token_type", "bearer"),
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshRequest) -> dict[str, str]:
    tokens = keycloak.refresh(payload.refresh_token)
    return {
        "access_token": tokens.get("access_token", ""),
        "refresh_token": tokens.get("refresh_token", ""),
        "token_type": tokens.get("token_type", "bearer"),
    }


@router.post("/logout")
def logout(payload: LogoutRequest) -> dict[str, str]:
    keycloak.logout(payload.refresh_token)
    return {"status": "success", "message": "Logged out successfully."}


@router.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    access_token = authorization.split(" ", 1)[1]
    userinfo = keycloak.get_user(access_token)

    roles = userinfo.get("realm_access", {}).get("roles", [])
    role = roles[0] if roles else "user"
    username = userinfo.get("preferred_username") or userinfo.get("name") or "user"

    return {
        "user_id": userinfo.get("sub", ""),
        "username": username,
        "role": role,
    }
