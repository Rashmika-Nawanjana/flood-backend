from unittest.mock import patch

import pytest

from app.auth import clerk


class DummyCredentials:
    def __init__(self, token: str):
        self.credentials = token


def test_get_current_user_returns_valid_user(monkeypatch):
    fake_payload = {
        "sub": "user_abc",
        "email": "test@example.com",
        "username": "tester",
        "public_metadata": {"role": "admin"},
    }

    monkeypatch.setattr(clerk, "get_clerk_public_keys", lambda: {"keys": []})
    monkeypatch.setattr(
        clerk.jwt,
        "decode",
        lambda token, jwks, algorithms, options: fake_payload,
    )

    user = clerk.get_current_user(credentials=DummyCredentials("fake-token"))

    assert user["user_id"] == "user_abc"
    assert user["email"] == "test@example.com"
    assert user["roles"] == ["admin"]


def test_get_current_user_raises_401_for_invalid_token(monkeypatch):
    monkeypatch.setattr(clerk, "get_clerk_public_keys", lambda: {"keys": []})

    def decode_failure(token, jwks, algorithms, options):
        raise clerk.JWTError("invalid token")

    monkeypatch.setattr(clerk.jwt, "decode", decode_failure)

    with pytest.raises(clerk.HTTPException) as exc_info:
        clerk.get_current_user(credentials=DummyCredentials("bad-token"))

    assert exc_info.value.status_code == clerk.status.HTTP_401_UNAUTHORIZED


def test_require_roles_allows_matching_role():
    checker = clerk.require_roles(["admin", "field_officer"])
    result = checker(current_user={"user_id": "u001", "roles": ["field_officer"]})

    assert result["user_id"] == "u001"
    assert "field_officer" in result["roles"]


def test_require_roles_blocks_missing_role():
    checker = clerk.require_roles(["admin", "field_officer"])

    with pytest.raises(clerk.HTTPException) as exc_info:
        checker(current_user={"user_id": "u002", "roles": ["citizen"]})

    assert exc_info.value.status_code == clerk.status.HTTP_403_FORBIDDEN
