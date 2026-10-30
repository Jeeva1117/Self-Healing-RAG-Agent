"""Comprehensive tests for Authentication, Authorization, RBAC, and Session Security."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_user_registration_success(client: AsyncClient):
    """Test 1: Normal user registration returns 201 and public user profile."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@enterprise.com",
            "password": "Password123!",
            "name": "Alice Engineer",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    user = data["data"]
    assert user["email"] == "alice@enterprise.com"
    assert user["name"] == "Alice Engineer"
    # Password must NEVER be returned in response!
    assert "password" not in user
    assert "password_hash" not in user
    assert "id" in user


@pytest.mark.asyncio
async def test_duplicate_email_registration_fails(client: AsyncClient):
    """Test 2: Registering with an existing email returns 409 Conflict."""
    payload = {
        "email": "duplicate@enterprise.com",
        "password": "Password123!",
        "name": "Original User",
    }
    first_res = await client.post("/api/v1/auth/register", json=payload)
    assert first_res.status_code == 201

    dup_res = await client.post("/api/v1/auth/register", json=payload)
    assert dup_res.status_code == 409
    data = dup_res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "USER_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_invalid_email_format_fails(client: AsyncClient):
    """Test 3: Invalid email syntax is rejected with 422 Validation Error."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-a-valid-email",
            "password": "Password123!",
            "name": "Invalid Email",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_weak_password_rejected(client: AsyncClient):
    """Test 4: Weak passwords (short or missing numbers/letters) are rejected."""
    # Too short (<8)
    res_short = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "weak1@enterprise.com",
            "password": "short",
            "name": "Short Password",
        },
    )
    assert res_short.status_code == 422

    # Missing digits
    res_no_digits = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "weak2@enterprise.com",
            "password": "OnlyLettersHere",
            "name": "No Digits",
        },
    )
    assert res_no_digits.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Test 5: Valid credentials log in successfully, returning access token & HttpOnly refresh cookie."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@enterprise.com", "password": "ValidPassword99", "name": "Login User"},
    )

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@enterprise.com", "password": "ValidPassword99"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert data["data"]["token_type"] == "bearer"
    assert data["data"]["user"]["email"] == "login@enterprise.com"

    # Verify HttpOnly cookie was set
    cookies = login_res.cookies
    assert settings.COOKIE_NAME_REFRESH in cookies


@pytest.mark.asyncio
async def test_login_wrong_password_fails(client: AsyncClient):
    """Test 6: Invalid password returns 401 Unauthorized with generic message."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpwd@enterprise.com", "password": "Password123!", "name": "Test User"},
    )

    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpwd@enterprise.com", "password": "IncorrectPassword99"},
    )
    assert res.status_code == 401
    data = res.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_unknown_user_fails(client: AsyncClient):
    """Test 7: Nonexistent email returns 401 without leaking user existence."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@enterprise.com", "password": "SomePassword123!"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_access_protected_endpoint_without_auth(client: AsyncClient):
    """Test 8: Accessing /auth/me without token returns 401."""
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_access_protected_endpoint_with_auth(client: AsyncClient):
    """Test 9: Accessing /auth/me with Bearer token succeeds."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "me@enterprise.com", "password": "ValidPassword99", "name": "Me User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "me@enterprise.com", "password": "ValidPassword99"},
    )
    access_token = login_res.json()["data"]["access_token"]

    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_res.status_code == 200
    user_data = me_res.json()["data"]
    assert user_data["email"] == "me@enterprise.com"


@pytest.mark.asyncio
async def test_expired_access_token_rejected(client: AsyncClient):
    """Test 10: An expired access token returns 401 TOKEN_EXPIRED."""
    now = datetime.now(UTC)
    expired_payload = {
        "sub": str(uuid.uuid4()),
        "role": "USER",
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int((now - timedelta(hours=2)).timestamp()),
        "exp": int((now - timedelta(hours=1)).timestamp()),
    }
    expired_token = jwt.encode(expired_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_refresh_token_rotation_flow(client: AsyncClient):
    """Test 11 & 12: Refresh token flow issues a new access token and rotates the refresh token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@enterprise.com", "password": "ValidPassword99", "name": "Refresh User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@enterprise.com", "password": "ValidPassword99"},
    )
    original_refresh_cookie = login_res.cookies.get(settings.COOKIE_NAME_REFRESH)
    assert original_refresh_cookie is not None

    # Refresh request using cookie
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        cookies={settings.COOKIE_NAME_REFRESH: original_refresh_cookie},
    )
    assert refresh_res.status_code == 200
    new_access_token = refresh_res.json()["data"]["access_token"]
    rotated_refresh_cookie = refresh_res.cookies.get(settings.COOKIE_NAME_REFRESH)

    # Must have rotated to a new refresh token
    assert rotated_refresh_cookie != original_refresh_cookie

    # New access token must work on /auth/me
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert me_res.status_code == 200


@pytest.mark.asyncio
async def test_refresh_token_reuse_detection_revokes_family(client: AsyncClient):
    """Test 13: Attempting to reuse an already rotated refresh token revokes all related sessions."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "reuse@enterprise.com", "password": "ValidPassword99", "name": "Reuse User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "reuse@enterprise.com", "password": "ValidPassword99"},
    )
    token_1 = login_res.cookies.get(settings.COOKIE_NAME_REFRESH)

    # Legitimate first rotation (consumes token_1, issues token_2)
    ref1_res = await client.post(
        "/api/v1/auth/refresh",
        cookies={settings.COOKIE_NAME_REFRESH: token_1},
    )
    assert ref1_res.status_code == 200
    token_2 = ref1_res.cookies.get(settings.COOKIE_NAME_REFRESH)

    # ATTACK / REUSE: An attacker attempts to replay token_1!
    replay_res = await client.post(
        "/api/v1/auth/refresh",
        cookies={settings.COOKIE_NAME_REFRESH: token_1},
    )
    assert replay_res.status_code == 401
    assert replay_res.json()["error"]["code"] == "TOKEN_REUSE_DETECTED"

    # Because family was revoked, the legitimate token_2 must now ALSO be invalidated!
    ref2_res = await client.post(
        "/api/v1/auth/refresh",
        cookies={settings.COOKIE_NAME_REFRESH: token_2},
    )
    assert ref2_res.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_session(client: AsyncClient):
    """Test 14: Logout invalidates the active refresh token and clears cookie."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "logout@enterprise.com", "password": "ValidPassword99", "name": "Logout User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "logout@enterprise.com", "password": "ValidPassword99"},
    )
    refresh_cookie = login_res.cookies.get(settings.COOKIE_NAME_REFRESH)

    logout_res = await client.post(
        "/api/v1/auth/logout",
        cookies={settings.COOKIE_NAME_REFRESH: refresh_cookie},
    )
    assert logout_res.status_code == 200

    # Trying to refresh with the logged-out cookie must fail
    refresh_after_logout = await client.post(
        "/api/v1/auth/refresh",
        cookies={settings.COOKIE_NAME_REFRESH: refresh_cookie},
    )
    assert refresh_after_logout.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_sessions(client: AsyncClient):
    """Test 15: Logout-all revokes all sessions across devices."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "logoutall@enterprise.com", "password": "ValidPassword99", "name": "LogoutAll User"},
    )
    # Login on device 1
    login1 = await client.post(
        "/api/v1/auth/login",
        json={"email": "logoutall@enterprise.com", "password": "ValidPassword99"},
    )
    access_token1 = login1.json()["data"]["access_token"]

    # Login on device 2
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": "logoutall@enterprise.com", "password": "ValidPassword99"},
    )
    cookie2 = login2.cookies.get(settings.COOKIE_NAME_REFRESH)

    # Execute logout-all from device 1
    logout_all_res = await client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {access_token1}"},
    )
    assert logout_all_res.status_code == 200

    # Device 2's refresh token must now be invalid
    ref2_res = await client.post(
        "/api/v1/auth/refresh",
        cookies={settings.COOKIE_NAME_REFRESH: cookie2},
    )
    assert ref2_res.status_code == 401


@pytest.mark.asyncio
async def test_rbac_admin_endpoint_forbidden_for_regular_user(client: AsyncClient):
    """Test 16 & 17: Regular USER gets 403 Forbidden; ADMIN gets 200 OK on /admin/users."""
    # First user registered is ADMIN
    admin_reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "admin@enterprise.com", "password": "Password123!", "name": "Admin User"},
    )
    assert admin_reg.json()["data"]["role"] == "ADMIN"
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@enterprise.com", "password": "Password123!"},
    )
    admin_token = admin_login.json()["data"]["access_token"]

    # Second user registered is regular USER
    user_reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "user@enterprise.com", "password": "Password123!", "name": "Normal User"},
    )
    assert user_reg.json()["data"]["role"] == "USER"
    user_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@enterprise.com", "password": "Password123!"},
    )
    user_token = user_login.json()["data"]["access_token"]

    # Regular user attempting admin endpoint -> 403
    forbidden_res = await client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert forbidden_res.status_code == 403
    assert forbidden_res.json()["error"]["code"] == "FORBIDDEN_INSUFFICIENT_ROLE"

    # Admin accessing admin endpoint -> 200
    admin_res = await client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_res.status_code == 200
    users = admin_res.json()["data"]["users"]
    assert len(users) >= 2


@pytest.mark.asyncio
async def test_change_password_workflow(client: AsyncClient):
    """Test 18: Password change validates current password and accepts new valid password."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "changepwd@enterprise.com", "password": "OldPassword123", "name": "Pwd User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "changepwd@enterprise.com", "password": "OldPassword123"},
    )
    token = login_res.json()["data"]["access_token"]

    # Attempt with wrong current password -> 401
    wrong_curr = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "WrongPassword!", "new_password": "NewPassword123"},
    )
    assert wrong_curr.status_code == 401

    # Successful password change
    succ_res = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "OldPassword123", "new_password": "NewPassword123"},
    )
    assert succ_res.status_code == 200

    # Old password fails login
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "changepwd@enterprise.com", "password": "OldPassword123"},
    )
    assert old_login.status_code == 401

    # New password succeeds login
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "changepwd@enterprise.com", "password": "NewPassword123"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_session_management_and_idor_protection(client: AsyncClient):
    """Test 19: Session listing and IDOR protection on session revocation."""
    # User 1
    await client.post(
        "/api/v1/auth/register",
        json={"email": "user1@enterprise.com", "password": "Password123!", "name": "User One"},
    )
    login1 = await client.post(
        "/api/v1/auth/login",
        json={"email": "user1@enterprise.com", "password": "Password123!"},
    )
    token1 = login1.json()["data"]["access_token"]

    # User 2
    await client.post(
        "/api/v1/auth/register",
        json={"email": "user2@enterprise.com", "password": "Password123!", "name": "User Two"},
    )
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": "user2@enterprise.com", "password": "Password123!"},
    )
    token2 = login2.json()["data"]["access_token"]

    # Get User 1's sessions
    sess_res1 = await client.get("/api/v1/auth/sessions", headers={"Authorization": f"Bearer {token1}"})
    assert sess_res1.status_code == 200
    user1_sessions = sess_res1.json()["data"]
    assert len(user1_sessions) >= 1
    session_id_to_attack = user1_sessions[0]["id"]

    # IDOR Attack: User 2 attempts to revoke User 1's session -> must be rejected (404/403)
    idor_res = await client.delete(
        f"/api/v1/auth/sessions/{session_id_to_attack}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert idor_res.status_code == 404

    # User 1 revoking own session -> succeeds
    revoke_res = await client.delete(
        f"/api/v1/auth/sessions/{session_id_to_attack}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert revoke_res.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_truthful_state(client: AsyncClient):
    """Test 20: Forgot password endpoint truthfully communicates unconfigured SMTP state."""
    res = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "anybody@enterprise.com"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "unconfigured"
    assert "not configured" in data["message"].lower()


@pytest.mark.asyncio
async def test_demo_login_disabled_by_default(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test 21: When DEMO_LOGIN_ENABLED is False (default), demo-login returns 403 Forbidden."""
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", False)
    res = await client.post("/api/v1/auth/demo-login")
    assert res.status_code == 403
    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "DEMO_LOGIN_DISABLED"
    assert "disabled" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_demo_login_blocked_in_production(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test 22: Even if DEMO_LOGIN_ENABLED is True, production environment strictly blocks demo login."""
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    res = await client.post("/api/v1/auth/demo-login")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "DEMO_LOGIN_DISABLED"


@pytest.mark.asyncio
async def test_demo_login_success_in_development(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test 23: In development with DEMO_LOGIN_ENABLED=True, issues real access token and cookie."""
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    res = await client.post("/api/v1/auth/demo-login")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert data["data"]["token_type"] == "bearer"
    user = data["data"]["user"]
    assert user["email"] == "demo@selfhealingrag.local"
    assert user["name"] == "Jeeva Developer"
    assert user["role"] == "USER"
    assert "password" not in user
    assert "password_hash" not in user

    # Refresh cookie set
    assert settings.COOKIE_NAME_REFRESH in res.cookies


@pytest.mark.asyncio
async def test_demo_login_is_idempotent(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test 24: Calling demo-login repeatedly reuses the same user without creating duplicates."""
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    res1 = await client.post("/api/v1/auth/demo-login")
    assert res1.status_code == 200
    user_id_1 = res1.json()["data"]["user"]["id"]

    res2 = await client.post("/api/v1/auth/demo-login")
    assert res2.status_code == 200
    user_id_2 = res2.json()["data"]["user"]["id"]

    assert user_id_1 == user_id_2


@pytest.mark.asyncio
async def test_demo_user_can_access_protected_routes(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test 25: Demo user access token authenticates on protected endpoints."""
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    login_res = await client.post("/api/v1/auth/demo-login")
    access_token = login_res.json()["data"]["access_token"]

    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_res.status_code == 200
    assert me_res.json()["data"]["email"] == "demo@selfhealingrag.local"


@pytest.mark.asyncio
async def test_demo_user_logout_flow(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test 26: Demo session can be revoked via standard logout endpoint."""
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    login_res = await client.post("/api/v1/auth/demo-login")
    refresh_cookie = login_res.cookies.get(settings.COOKIE_NAME_REFRESH)
    assert refresh_cookie is not None

    # Logout
    logout_res = await client.post("/api/v1/auth/logout", cookies={settings.COOKIE_NAME_REFRESH: refresh_cookie})
    assert logout_res.status_code == 200

    # Refresh should now be rejected
    refresh_res = await client.post("/api/v1/auth/refresh", cookies={settings.COOKIE_NAME_REFRESH: refresh_cookie})
    assert refresh_res.status_code == 401


@pytest.mark.asyncio
async def test_auth_config_endpoint(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test 27: Public /auth/config endpoint returns accurate demo flag based on settings."""
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", False)
    res_disabled = await client.get("/api/v1/auth/config")
    assert res_disabled.status_code == 200
    assert res_disabled.json()["data"]["demo_login_enabled"] is False

    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    res_enabled = await client.get("/api/v1/auth/config")
    assert res_enabled.status_code == 200
    assert res_enabled.json()["data"]["demo_login_enabled"] is True
