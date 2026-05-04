from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


def _discovery_url() -> str:
    if settings.oidc_discovery_url:
        return settings.oidc_discovery_url
    return (
        f"{settings.keycloak_url}/realms/"
        f"{settings.keycloak_realm}/.well-known/openid-configuration"
    )


@lru_cache
def _get_discovery() -> dict[str, Any]:
    url = _discovery_url()
    try:
        response = httpx.get(url, timeout=10)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth provider unavailable",
        ) from exc
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth provider discovery failed",
        )
    return response.json()


def _token_request(payload: dict[str, str]) -> dict[str, Any]:
    discovery = _get_discovery()
    token_endpoint = discovery.get("token_endpoint")
    if not token_endpoint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token endpoint unavailable",
        )

    payload["client_id"] = settings.keycloak_client_id
    if settings.keycloak_client_secret:
        payload["client_secret"] = settings.keycloak_client_secret

    try:
        response = httpx.post(token_endpoint, data=payload, timeout=10)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth provider unavailable",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return response.json()


def login(username: str, password: str) -> dict[str, Any]:
    payload = {
        "grant_type": "password",
        "username": username,
        "password": password,
    }
    return _token_request(payload)


def refresh(refresh_token: str) -> dict[str, Any]:
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    return _token_request(payload)


def logout(refresh_token: str) -> None:
    discovery = _get_discovery()
    logout_endpoint = discovery.get("end_session_endpoint")
    if not logout_endpoint:
        return

    payload = {
        "client_id": settings.keycloak_client_id,
        "refresh_token": refresh_token,
    }
    if settings.keycloak_client_secret:
        payload["client_secret"] = settings.keycloak_client_secret

    try:
        response = httpx.post(logout_endpoint, data=payload, timeout=10)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth provider unavailable",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logout failed",
        )


def get_user(access_token: str) -> dict[str, Any]:
    discovery = _get_discovery()
    userinfo_endpoint = discovery.get("userinfo_endpoint")
    if not userinfo_endpoint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Userinfo endpoint unavailable",
        )

    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = httpx.get(userinfo_endpoint, headers=headers, timeout=10)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth provider unavailable",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    return response.json()
