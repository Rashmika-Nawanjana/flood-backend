import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError

from app.core.config import settings

security = HTTPBearer()


def get_clerk_public_keys() -> dict:
    """Fetch Clerk's JWKS for JWT signature verification."""
    try:
        response = requests.get(settings.clerk_jwks_url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Clerk auth provider",
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Validate Clerk JWT and return user info."""
    token = credentials.credentials

    try:
        jwks = get_clerk_public_keys()

        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={
                "verify_aud": False,
            },
        )

        # Clerk stores custom role in publicMetadata
        public_metadata = payload.get("public_metadata") or payload.get("publicMetadata") or {}
        raw_role = public_metadata.get("role") or payload.get("role", "citizen")
        role = str(raw_role).lower()

        return {
            "user_id": payload.get("sub"),
            "username": payload.get("username") or payload.get("email", ""),
            "email": payload.get("email", ""),
            "roles": [role],
        }

    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from exc


def require_roles(allowed_roles: list[str]):
    """Factory: returns a FastAPI dependency that enforces role-based access."""

    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles = current_user.get("roles", [])
        if not any(role in user_roles for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return current_user

    return role_checker
