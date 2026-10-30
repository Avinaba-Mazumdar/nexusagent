from datetime import UTC, datetime, timedelta
from uuid import uuid4

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
async def test_garbage_google_token_is_rejected():
    """Regression (audit S-04): anything that is not a signed Google ID token is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/google",
            json={"credential": "mock-google-token:attacker@nexusagent.internal:Attacker"},
        )
        assert resp.status_code == 401


CLIENT_ID = "test-client-id-123.apps.googleusercontent.com"


@pytest.fixture
def google_signer(monkeypatch):
    """Sign RS256 ID tokens with a throwaway key and make the JWKS client trust it."""
    from types import SimpleNamespace

    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app.config import settings
    from app.core import auth as auth_module

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(
        auth_module._google_jwks,
        "get_signing_key_from_jwt",
        lambda _token: SimpleNamespace(key=key.public_key()),
    )

    def sign(**overrides):
        now = datetime.now(UTC)
        claims = {
            "aud": CLIENT_ID,
            "iss": "https://accounts.google.com",
            "sub": "google-sub-1",
            "email": "user@example.com",
            "email_verified": True,
            "name": "Valid User",
            "iat": now,
            "exp": now + timedelta(minutes=10),
        }
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return pyjwt.encode(claims, key, algorithm="RS256")

    return sign


@pytest.mark.asyncio
async def test_verify_google_token_accepts_a_valid_token(google_signer):
    from app.core.auth import verify_google_token

    profile = await verify_google_token(google_signer())
    assert profile["email"] == "user@example.com"
    assert profile["name"] == "Valid User"
    assert profile["sub"] == "google-sub-1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"aud": "wrong-client-id"}, "audience mismatch"),
        ({"iss": "https://evil.issuer.com"}, "issuer mismatch"),
        ({"exp": datetime.now(UTC) - timedelta(minutes=1)}, "Invalid or expired"),
        ({"sub": None}, "Invalid or expired"),
    ],
)
async def test_verify_google_token_rejects_bad_claims(google_signer, overrides, message):
    from app.core.auth import verify_google_token

    with pytest.raises(HTTPException) as exc:
        await verify_google_token(google_signer(**overrides))
    assert exc.value.status_code == 401
    assert message in exc.value.detail


@pytest.mark.asyncio
async def test_verify_google_token_rejects_unverified_email(google_signer):
    from app.core.auth import verify_google_token

    with pytest.raises(HTTPException) as exc:
        await verify_google_token(google_signer(email_verified=False))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_verify_google_token_rejects_a_token_signed_by_another_key(google_signer):
    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app.core.auth import verify_google_token

    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    forged = pyjwt.encode(
        {
            "aud": CLIENT_ID,
            "iss": "https://accounts.google.com",
            "sub": "x",
            "email": "a@b.com",
            "email_verified": True,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        attacker_key,
        algorithm="RS256",
    )
    with pytest.raises(HTTPException) as exc:
        await verify_google_token(forged)
    assert exc.value.status_code == 401


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

    # R2-LOG-08: the read reports full capacity but does not write the refill.
    async with pool.acquire() as conn:
        stored = await conn.fetchrow(
            "SELECT tokens_remaining, last_replenished_at FROM rate_limit_buckets WHERE user_id = $1;",
            user.id,
        )
    assert stored["tokens_remaining"] == 0
    assert stored["last_replenished_at"] == past_time


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


@pytest.mark.asyncio
async def test_google_auth_is_throttled_per_ip_sec_14(monkeypatch):
    """SEC-14: the 21st Google sign-in attempt from one IP in an hour gets a 429."""
    from app.config import settings

    async def reject(_credential):
        raise HTTPException(status_code=401, detail="nope")

    monkeypatch.setattr("app.routes.auth.verify_google_token", reject)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        codes = [
            (await client.post("/api/auth/google", json={"credential": "x" * 20})).status_code
            for _ in range(settings.GOOGLE_AUTH_PER_IP_PER_HOUR + 1)
        ]
    assert codes[:-1] == [401] * settings.GOOGLE_AUTH_PER_IP_PER_HOUR
    assert codes[-1] == 429


@pytest.mark.asyncio
async def test_optional_user_ignores_a_signed_out_token_r2_sec_04():
    """A token from before logout must not identify the user on optional-auth endpoints."""
    from unittest.mock import AsyncMock

    from fastapi.security import HTTPAuthorizationCredentials

    from app.core.auth import get_current_user_optional, session_claims

    user = _user(token_version=0)
    token, _ = create_access_token(session_claims(user))
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    db = AsyncMock()
    db.get_user_by_id.return_value = user

    resolved = await get_current_user_optional(creds, db)
    assert resolved is not None and resolved.id == user.id

    user.token_version = 1  # user logged out
    assert await get_current_user_optional(creds, db) is None
    assert await get_current_user_optional(None, db) is None
