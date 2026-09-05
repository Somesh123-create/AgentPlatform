import asyncio
from inspect import signature

import pytest
from fastapi import HTTPException

from agent_auth import JWTManager

from app.api.routes.mcp import router
from app.core.auth import current_user, jwt_manager


def test_mcp_routes_require_current_user():
    assert len(router.routes) == 5
    for route in router.routes:
        dependency_names = {
            parameter.name
            for parameter in signature(route.endpoint).parameters.values()
        }
        assert "authenticated_user" in dependency_names


def test_mcp_uses_shared_jwt_configuration():
    assert jwt_manager.algorithm == "HS256"
    assert callable(current_user)


def test_valid_user_token_returns_current_user_claims():
    token = jwt_manager.create_access_token(42, "USER")
    authenticated_user = asyncio.run(current_user(token))

    assert authenticated_user.user_id == 42
    assert authenticated_user.role == "USER"


def test_invalid_token_returns_bearer_401():
    with pytest.raises(HTTPException) as error:
        asyncio.run(current_user("invalid-token"))

    assert error.value.status_code == 401
    assert error.value.headers["WWW-Authenticate"] == "Bearer"


def test_wrong_secret_token_is_rejected():
    token = JWTManager("different-secret").create_access_token(42, "USER")

    with pytest.raises(HTTPException) as error:
        asyncio.run(current_user(token))

    assert error.value.status_code == 401