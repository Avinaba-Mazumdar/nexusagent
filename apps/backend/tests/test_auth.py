from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token, decode_access_token
from app.db.models import User
from app.db.neon import neon_db
from app.main import app


@pytest.mark.asyncio
async def test_jwt_token_encode_decode():
    data = {"sub": "00000000-0000-0000-0000-000000000001", "role": "user"}
    token, expires_in = create_access_token(data)
    assert isinstance(token, str)
    assert expires_in > 0

    decoded = decode_access_token(token)
    assert decoded["sub"] == "00000000-0000-0000-0000-000000000001"
    assert decoded["role"] == "user"


@pytest.mark.db
@pytest.mark.asyncio
async def test_guest_pass_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/guest")
        assert response.status_code == 200
        data = response.json()

        assert "user" in data
        assert data["user"]["isGuest"] is True
        assert "Guest Architect" in data["user"]["name"]
        assert "tokens" in data
        assert data["tokens"]["tokenType"] == "bearer"
        assert len(data["tokens"]["accessToken"]) > 20
        assert data["quotaRemaining"] == 5
        assert data["bucketCapacity"] == 5

        # Test authenticated /me with this guest token
        token = data["tokens"]["accessToken"]
        me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["user"]["id"] == data["user"]["id"]
        assert me_data["quota"]["tokensRemaining"] == 5

        # Reusing same deviceId should return the same guest user
        dev_id = f"test-device-{uuid4().hex[:8]}"
        res1 = await client.post("/api/auth/guest", json={"deviceId": dev_id})
        assert res1.status_code == 200
        user1 = res1.json()["user"]

        res2 = await client.post("/api/auth/guest", json={"deviceId": dev_id})
        assert res2.status_code == 200
        user2 = res2.json()["user"]

        assert user1["id"] == user2["id"]
        assert user1["name"] == user2["name"]
        assert "deviceId" not in user2
        assert "clientIp" not in user2


@pytest.mark.asyncio
async def test_prune_endpoint_is_not_exposed():
    """Regression (audit S-03): guest pruning is a scheduled script, not an HTTP route."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/auth/maintenance/prune-guests?ttl_hours=0")
        assert res.status_code in (404, 405)


@pytest.mark.asyncio
async def test_unauthorized_access():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

        resp_bad = await client.get(
            "/api/auth/me", headers={"Authorization": "Bearer invalid_garbage_token"}
        )
        assert resp_bad.status_code == 401


@pytest.mark.db
@pytest.mark.asyncio
async def test_google_oauth_endpoint(monkeypatch):
    profile = {
        "email": "google.lead@distributed.io",
        "name": "Senior Google Architect",
        "picture": None,
        "sub": "sub-lead-1",
    }

    async def fake_verify(credential: str) -> dict:
        if credential == "invalid_raw_token_xyz":
            raise HTTPException(status_code=401, detail="Invalid or expired Google credential")
        return profile

    monkeypatch.setattr("app.routes.auth.verify_google_token", fake_verify)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Valid Google OAuth authentication
        resp = await client.post("/api/auth/google", json={"credential": "valid_token_1"})
        assert resp.status_code == 200
        data = resp.json()

        assert "accessToken" in data
        assert data["tokenType"] == "bearer"
        assert data["user"]["email"] == "google.lead@distributed.io"
        assert data["user"]["name"] == "Senior Google Architect"
        assert data["user"]["isGuest"] is False

        # 2. Check /me with returned JWT token
        token = data["accessToken"]
        me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["user"]["email"] == "google.lead@distributed.io"
        assert me_data["quota"]["bucketCapacity"] == 25

        # 3. Repeat authentication with updated name (upsert verification)
        profile["name"] = "Principal Google Architect"
        upsert_resp = await client.post("/api/auth/google", json={"credential": "valid_token_2"})
        assert upsert_resp.status_code == 200
        upsert_data = upsert_resp.json()
        assert upsert_data["user"]["email"] == "google.lead@distributed.io"
        assert upsert_data["user"]["name"] == "Principal Google Architect"

        # 4. Invalid credential returns 401
        bad_resp = await client.post(
            "/api/auth/google", json={"credential": "invalid_raw_token_xyz"}
        )
        assert bad_resp.status_code == 401


@pytest.mark.asyncio
async def test_mock_google_token_is_rejected(monkeypatch):
    """Regression (audit S-04): mock google token is rejected unconditionally."""

    class FakeResponse:
        status_code = 400

        def json(self):
            return {"error": "invalid_token"}

    original_post = httpx.AsyncClient.post

    async def fake_post(self, url, *args, **kwargs):
        if "oauth2.googleapis.com" in str(url):
            return FakeResponse()
        return await original_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/google",
            json={"credential": "mock-google-token:attacker@nexusagent.internal:Attacker"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_google_token_audience_and_issuer(monkeypatch):
    """Verify audience and issuer checks on Google ID tokens (audit S-05)."""
    from app.config import settings
    from app.core.auth import verify_google_token

    monkeypatch.setattr(
        settings, "GOOGLE_CLIENT_ID", "test-client-id-123.apps.googleusercontent.com"
    )

    # 1. Wrong aud -> 401
    class FakeAudResp:
        status_code = 200

        def json(self):
            return {
                "aud": "wrong-client-id",
                "iss": "https://accounts.google.com",
                "email": "a@b.com",
                "email_verified": "true",
            }

    async def fake_post_aud(*args, **kwargs):
        return FakeAudResp()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post_aud)
    with pytest.raises(HTTPException) as exc:
        await verify_google_token("token_wrong_aud")
    assert exc.value.status_code == 401
    assert "audience mismatch" in exc.value.detail

    # 2. Wrong iss -> 401
    class FakeIssResp:
        status_code = 200

        def json(self):
            return {
                "aud": "test-client-id-123.apps.googleusercontent.com",
                "iss": "https://evil.issuer.com",
                "email": "a@b.com",
                "email_verified": "true",
            }

    async def fake_post_iss(*args, **kwargs):
        return FakeIssResp()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post_iss)
    with pytest.raises(HTTPException) as exc:
        await verify_google_token("token_wrong_iss")
    assert exc.value.status_code == 401
    assert "issuer mismatch" in exc.value.detail

    # 3. Valid aud, iss, email_verified -> profile
    class FakeValidResp:
        status_code = 200

        def json(self):
            return {
                "aud": "test-client-id-123.apps.googleusercontent.com",
                "iss": "https://accounts.google.com",
                "email": "user@example.com",
                "email_verified": "true",
                "name": "Valid User",
                "sub": "sub-123",
            }

    async def fake_post_valid(*args, **kwargs):
        return FakeValidResp()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post_valid)
    res = await verify_google_token("valid_token")
    assert res["email"] == "user@example.com"
    assert res["name"] == "Valid User"


@pytest.mark.asyncio
async def test_offline_prune_guests_safe_fallback():
    # Calling prune_expired_guests when pool is not initialized returns 0 safely
    count = await neon_db.prune_expired_guests(ttl_hours=24)
    assert count == 0


@pytest.mark.db
@pytest.mark.asyncio
async def test_hourly_rate_limit_replenishment():
    client_ip = f"198.51.100.{uuid4().hex[:2]}"
    user = await neon_db.create_user(
        User(
            id=uuid4(),
            email=None,
            name="Replenish Test User",
            is_guest=True,
            client_ip=client_ip,
        )
    )

    # Initialize bucket with 5 tokens
    bucket = await neon_db.get_or_create_rate_limit(user.id, default_tokens=5)
    assert bucket.tokens_remaining == 5

    # Simulate manual depletion & setting timestamp in the past (2 hours ago)
    pool = neon_db.get_pool()
    async with pool.acquire() as conn:
        past_time = datetime.now(UTC) - timedelta(hours=2)
        await conn.execute(
            """
            UPDATE rate_limit_buckets
            SET tokens_remaining = 0, last_replenished_at = $2
            WHERE user_id = $1;
            """,
            user.id,
            past_time,
        )

    # Calling get_or_create_rate_limit should detect elapsed hour and replenish to 5
    replenished = await neon_db.get_or_create_rate_limit(user.id, default_tokens=5)
    assert replenished.tokens_remaining == 5


# ---------------------------------------------------------------------------
# SEC-04: revocation, session age cap, iss/aud
# ---------------------------------------------------------------------------


def _user(token_version: int = 0, is_guest: bool = False) -> User:
    return User(
        id=uuid4(), name="T", email="t@example.com", is_guest=is_guest, token_version=token_version
    )


@pytest.mark.asyncio
async def test_token_from_before_logout_is_rejected():
    """Bumping token_version (logout) invalidates previously issued tokens."""
    from unittest.mock import AsyncMock

    from fastapi.security import HTTPAuthorizationCredentials

    from app.core.auth import get_current_user, session_claims

    user = _user(token_version=0)
    token, _ = create_access_token(session_claims(user))
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    db = AsyncMock()
    db.get_user_by_id.return_value = user

    assert (await get_current_user(creds, db)).id == user.id

    user.token_version = 1  # user logged out
    with pytest.raises(HTTPException) as exc:
        await get_current_user(creds, db)
    assert exc.value.status_code == 401


def test_tokens_carry_and_require_issuer_and_audience():
    import jwt as pyjwt

    from app.config import settings

    token, _ = create_access_token({"sub": "x"})
    claims = pyjwt.decode(token, options={"verify_signature": False})
    assert claims["iss"] == settings.JWT_ISSUER and claims["aud"] == settings.JWT_AUDIENCE

    foreign = pyjwt.encode(
        {"sub": "x", "exp": datetime.now(UTC) + timedelta(minutes=5), "aud": "someone-else"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        decode_access_token(foreign)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_cannot_extend_a_session_past_the_max_age(monkeypatch, fake_rate_db):
    from app.core.auth import get_current_user, session_claims

    user = _user()
    old_login = int((datetime.now(UTC) - timedelta(days=8)).timestamp())
    token, _ = create_access_token(session_claims(user, auth_time=old_login))
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {token}"}
            )
        assert res.status_code == 401

        fresh, _ = create_access_token(session_claims(user))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            ok = await client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {fresh}"}
            )
        assert ok.status_code == 200
        new_claims = decode_access_token(ok.json()["accessToken"])
        assert new_claims["auth_time"] == decode_access_token(fresh)["auth_time"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_guest_refresh_uses_guest_lifetime():
    from datetime import timedelta as td

    from app.config import settings
    from app.core.auth import token_lifetime

    assert token_lifetime(_user(is_guest=True)) == td(minutes=settings.GUEST_TOKEN_EXPIRE_MINUTES)
    assert token_lifetime(_user(is_guest=False)) == td(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
