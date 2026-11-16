from datetime import UTC, datetime, timedelta
from typing import Protocol, override
from uuid import UUID, uuid4

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, Request
from httpx import ASGITransport, AsyncClient
from jwt import PyJWK
from jwt.algorithms import RSAAlgorithm

from app.config import settings
from app.core.auth import (
    GoogleProfile,
    create_access_token,
    decode_access_token,
    get_current_user,
    get_current_user_optional,
    session_claims,
    verify_google_token,
)
from app.db.models import GuestPassResponse, MeResponse, TokenResponse, User
from app.db.neon import NeonDatabase, get_db, neon_db
from app.main import app


class _UsersDb(NeonDatabase):
    """The user lookups of NeonDatabase for one known user, recording every call."""

    def __init__(self, user: User | None = None) -> None:
        super().__init__(dsn="")
        self.user: User | None = user
        self.lookups: int = 0
        self.touched: list[UUID] = []
        self.last_seen_updates: int = 0

    @override
    async def get_user_by_id(self, user_id: UUID) -> User | None:
        self.lookups += 1
        return self.user if self.user is not None and self.user.id == user_id else None

    @override
    async def touch_user(self, user_id: UUID) -> bool:
        self.touched.append(user_id)
        return True

    @override
    async def update_user_last_seen(
        self,
        user_id: UUID,
        client_ip: str | None = None,
        device_id: str | None = None,
        machine_hash: str | None = None,
    ) -> None:
        self.last_seen_updates += 1


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
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Origin": "http://localhost:3000"},
    ) as client:
        response = await client.post("/api/auth/guest")
        assert response.status_code == 200
        data = GuestPassResponse.model_validate_json(response.content)

        assert data.user.is_guest is True
        assert "Guest User" in data.user.name
        assert '"tokens"' not in response.text
        assert '"accessToken"' not in response.text
        assert data.expiresIn > 0
        assert data.quotaRemaining == 5
        assert data.bucketCapacity == 5
        assert "nexus_session" in response.cookies
        token = response.cookies["nexus_session"]
        assert len(token) > 20

        # Test authenticated /me with this guest session cookie
        me_resp = await client.get("/api/auth/me")
        assert me_resp.status_code == 200
        me_data = MeResponse.model_validate_json(me_resp.content)
        assert me_data.user.id == data.user.id
        assert me_data.quota.tokensRemaining == 5

        # The device cookie, not a body field, reopens this guest.
        res1 = await client.post("/api/auth/guest", json={"deviceId": "not-the-account-key"})
        assert res1.status_code == 200
        user1 = GuestPassResponse.model_validate_json(res1.content).user

        res2 = await client.post("/api/auth/guest")
        assert res2.status_code == 200
        user2 = GuestPassResponse.model_validate_json(res2.content).user

        assert user1.id == user2.id == data.user.id
        assert user1.name == user2.name
        assert '"deviceId"' not in res2.text
        assert '"clientIp"' not in res2.text


@pytest.mark.db
@pytest.mark.asyncio
async def test_guests_with_same_machine_hash_get_distinct_accounts():
    """B1: machineId collision must never hand Guest B the account of Guest A."""
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client_a,
        AsyncClient(transport=transport, base_url="http://test") as client_b,
    ):
        res_a = await client_a.post("/api/auth/guest", json={"machineId": "same-machine"})
        assert res_a.status_code == 200
        user_a = GuestPassResponse.model_validate_json(res_a.content).user

        res_b = await client_b.post("/api/auth/guest", json={"machineId": "same-machine"})
        assert res_b.status_code == 200
        user_b = GuestPassResponse.model_validate_json(res_b.content).user

        assert user_a.id != user_b.id


@pytest.mark.db
@pytest.mark.asyncio
async def test_body_device_id_cannot_reopen_another_guest():
    """A client that knows another guest's raw device id still gets its own account."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client_a:
        res_a = await client_a.post("/api/auth/guest")
        assert res_a.status_code == 200
        stolen = res_a.cookies["nexus_device"]
        user_a = GuestPassResponse.model_validate_json(res_a.content).user.id

    async with AsyncClient(transport=transport, base_url="http://test") as client_b:
        res_b = await client_b.post("/api/auth/guest", json={"deviceId": stolen})
        assert res_b.status_code == 200
        assert GuestPassResponse.model_validate_json(res_b.content).user.id != user_a


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
async def test_google_oauth_endpoint(monkeypatch: pytest.MonkeyPatch):
    profile = GoogleProfile(
        email="google.lead@distributed.io",
        name="Senior Google Architect",
        picture=None,
        sub="sub-lead-1",
    )

    async def fake_verify(credential: str) -> GoogleProfile:
        if credential == "invalid_raw_token_xyz":
            raise HTTPException(status_code=401, detail="Invalid or expired Google credential")
        return profile

    monkeypatch.setattr("app.routes.auth.verify_google_token", fake_verify)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Origin": "http://localhost:3000"},
    ) as client:
        # 1. Valid Google OAuth authentication
        resp = await client.post("/api/auth/google", json={"credential": "valid_token_1"})
        assert resp.status_code == 200
        data = TokenResponse.model_validate_json(resp.content)

        assert '"accessToken"' not in resp.text
        assert "nexus_session" in resp.cookies
        token = resp.cookies["nexus_session"]
        assert len(token) > 20
        assert data.user.email == "google.lead@distributed.io"
        assert data.user.name == "Senior Google Architect"
        assert data.user.is_guest is False

        # 2. Check /me with returned session cookie
        me_resp = await client.get("/api/auth/me")
        assert me_resp.status_code == 200
        me_data = MeResponse.model_validate_json(me_resp.content)
        assert me_data.user.email == "google.lead@distributed.io"
        assert me_data.quota.bucketCapacity == 25

        # 3. Repeat authentication with updated name (upsert verification)
        profile["name"] = "Principal Google Architect"
        upsert_resp = await client.post("/api/auth/google", json={"credential": "valid_token_2"})
        assert upsert_resp.status_code == 200
        upsert_data = TokenResponse.model_validate_json(upsert_resp.content)
        assert upsert_data.user.email == "google.lead@distributed.io"
        assert upsert_data.user.name == "Principal Google Architect"

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


class Signer(Protocol):
    """Signs a Google ID token; ``None`` overrides drop a claim."""

    def __call__(self, **overrides: object) -> str: ...


@pytest.fixture
def google_signer(monkeypatch: pytest.MonkeyPatch) -> Signer:
    """Sign RS256 ID tokens with a throwaway key and make the JWKS client trust it."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signing_key = PyJWK(RSAAlgorithm.to_jwk(key.public_key(), as_dict=True), "RS256")

    def get_signing_key_from_jwt(_token: str) -> PyJWK:
        return signing_key

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(
        "app.core.auth._google_jwks.get_signing_key_from_jwt", get_signing_key_from_jwt
    )

    def sign(**overrides: object) -> str:
        now = datetime.now(UTC)
        claims: dict[str, object] = {
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
async def test_verify_google_token_accepts_a_valid_token(google_signer: Signer):
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
async def test_verify_google_token_rejects_bad_claims(
    google_signer: Signer, overrides: dict[str, object], message: str
):
    with pytest.raises(HTTPException) as exc:
        _ = await verify_google_token(google_signer(**overrides))
    assert exc.value.status_code == 401
    assert message in exc.value.detail


@pytest.mark.asyncio
async def test_verify_google_token_rejects_unverified_email(google_signer: Signer):
    with pytest.raises(HTTPException) as exc:
        _ = await verify_google_token(google_signer(email_verified=False))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.usefixtures("google_signer")
async def test_verify_google_token_rejects_a_token_signed_by_another_key():
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
        _ = await verify_google_token(forged)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_offline_prune_guests_safe_fallback():
    # Calling prune_expired_guests when pool is not initialized returns 0 safely
    count = await neon_db.prune_expired_guests(ttl_hours=24)
    assert count == 0


# ---------------------------------------------------------------------------
# SEC-04: revocation, session age cap, iss/aud
# ---------------------------------------------------------------------------


def _auth_request() -> Request:
    """Direct dependency calls need a request so a rejected credential can be logged."""
    return Request({"type": "http", "headers": [], "client": ("127.0.0.1", 0)})


def _user(token_version: int = 0, is_guest: bool = False) -> User:
    return User(
        id=uuid4(), name="T", email="t@example.com", is_guest=is_guest, token_version=token_version
    )


@pytest.mark.asyncio
async def test_token_from_before_logout_is_rejected():
    """Bumping token_version (logout) invalidates previously issued tokens."""
    user = _user(token_version=0)
    token, _ = create_access_token(session_claims(user))
    db = _UsersDb(user)

    assert (await get_current_user(_auth_request(), token, db)).id == user.id

    user.token_version = 1  # user logged out
    with pytest.raises(HTTPException) as exc:
        _ = await get_current_user(_auth_request(), token, db)
    assert exc.value.status_code == 401


def test_tokens_carry_and_require_issuer_and_audience():
    token, _ = create_access_token({"sub": "x"})
    claims = pyjwt.decode(token, options={"verify_signature": False})
    assert claims["iss"] == settings.JWT_ISSUER and claims["aud"] == settings.JWT_AUDIENCE

    foreign = pyjwt.encode(
        {"sub": "x", "exp": datetime.now(UTC) + timedelta(minutes=5), "aud": "someone-else"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        _ = decode_access_token(foreign)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_rate_db")
async def test_refresh_cannot_extend_a_session_past_the_max_age():
    user = _user()
    old_login = int((datetime.now(UTC) - timedelta(days=8)).timestamp())
    token, _ = create_access_token(session_claims(user, auth_time=old_login))
    db = _UsersDb(user)
    app.dependency_overrides[get_db] = lambda: db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Origin": "http://localhost:3000"},
        ) as client:
            res = await client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {token}"}
            )
            assert res.status_code == 401

            fresh, _ = create_access_token(session_claims(user))
            ok = await client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {fresh}"}
            )
            assert ok.status_code == 200
            refreshed_token = ok.cookies["nexus_session"]
            new_claims = decode_access_token(refreshed_token)
            assert new_claims["auth_time"] == decode_access_token(fresh)["auth_time"]
    finally:
        _ = app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_google_auth_is_throttled_per_ip_sec_14(monkeypatch: pytest.MonkeyPatch):
    """SEC-14: the 21st Google sign-in attempt from one IP in an hour gets a 429."""

    async def reject(_credential: str) -> GoogleProfile:
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
    user = _user(token_version=0)
    token, _ = create_access_token(session_claims(user))
    db = _UsersDb(user)

    resolved = await get_current_user_optional(_auth_request(), token, db)
    assert resolved is not None and resolved.id == user.id

    user.token_version = 1  # user logged out
    assert await get_current_user_optional(_auth_request(), token, db) is None
    assert await get_current_user_optional(_auth_request(), None, db) is None


@pytest.mark.asyncio
async def test_authenticated_requests_use_the_throttled_last_seen_write_r2_log_09():
    user = _user()
    token, _ = create_access_token(session_claims(user))
    db = _UsersDb(user)
    _ = await get_current_user(_auth_request(), token, db)

    assert db.touched == [user.id]
    assert db.last_seen_updates == 0


@pytest.mark.db
@pytest.mark.asyncio
async def test_touch_user_writes_at_most_once_per_window_r2_log_09():
    user = await neon_db.create_user(
        User(id=uuid4(), name="Touched", is_guest=True, device_id=uuid4().hex)
    )
    try:
        pool = neon_db.get_pool()
        async with pool.acquire() as conn:
            _ = await conn.execute(
                "UPDATE users SET last_seen_at = NOW() - INTERVAL '1 hour' WHERE id = $1;", user.id
            )
        assert await neon_db.touch_user(user.id) is True
        assert await neon_db.touch_user(user.id) is False
    finally:
        async with neon_db.get_pool().acquire() as conn:
            _ = await conn.execute("DELETE FROM users WHERE id = $1;", user.id)


@pytest.mark.asyncio
async def test_refresh_limit_applies_before_any_database_work_r2_log_11(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.core.rate_limiter import refresh_limiter

    def always_limited(_ip: str) -> bool:
        return False

    db = _UsersDb()
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(refresh_limiter, "hit", always_limited)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/auth/refresh", headers={"Authorization": "Bearer x"})
        assert res.status_code == 429
        assert db.lookups == 0
    finally:
        _ = app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_guest_body_device_id_cannot_be_huge():
    """The body field is ignored, but a huge value is still rejected before the handler runs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        too_long = await client.post("/api/auth/guest", json={"deviceId": "a" * 10_000})
    assert too_long.status_code == 422


# ---------------------------------------------------------------------------
# D2: Stateless Session Hardening with httpOnly Cookies and CSRF
# ---------------------------------------------------------------------------


@pytest.mark.db
@pytest.mark.asyncio
async def test_cookie_attributes_guest_pass():
    """(a) guest sign-in sets a cookie with HttpOnly and SameSite=lax."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/auth/guest", json={"deviceId": "abc"})
        assert res.status_code == 200
        cookies = [value.lower() for value in res.headers.get_list("set-cookie")]
        session = next(value for value in cookies if "nexus_session=" in value)
        device = next(value for value in cookies if "nexus_device=" in value)
        for value in (session, device):
            assert "httponly" in value
            assert "samesite=lax" in value
            assert "path=/" in value


@pytest.mark.db
@pytest.mark.asyncio
async def test_auth_me_works_with_only_cookie():
    """(b) /api/auth/me works with only the cookie (no Authorization header)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        guest_res = await client.post("/api/auth/guest")
        assert guest_res.status_code == 200
        token = guest_res.cookies["nexus_session"]

    async with AsyncClient(
        transport=transport, base_url="http://test", cookies={"nexus_session": token}
    ) as client:
        me_res = await client.get("/api/auth/me")
        assert me_res.status_code == 200
        assert MeResponse.model_validate_json(me_res.content).user.is_guest is True


@pytest.mark.db
@pytest.mark.asyncio
async def test_logout_clears_cookie():
    """(c) logout clears the cookie."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        guest_res = await client.post("/api/auth/guest")
        assert guest_res.status_code == 200
        assert "nexus_session" in client.cookies

        logout_res = await client.post(
            "/api/auth/logout", headers={"Origin": "http://localhost:3000"}
        )
        assert logout_res.status_code == 200
        set_cookie = "; ".join(logout_res.headers.get_list("set-cookie")).lower()
        assert (
            "max-age=0" in set_cookie
            or 'nexus_session=""' in set_cookie
            or "nexus_session=;" in set_cookie
        )


@pytest.mark.db
@pytest.mark.asyncio
async def test_auth_json_responses_contain_no_access_token():
    """(d) the JSON bodies contain no accessToken."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        guest_res = await client.post("/api/auth/guest")
        assert guest_res.status_code == 200
        assert "accessToken" not in guest_res.text
        assert '"tokens"' not in guest_res.text

        refresh_res = await client.post(
            "/api/auth/refresh", headers={"Origin": "http://localhost:3000"}
        )
        assert refresh_res.status_code == 200
        assert "accessToken" not in refresh_res.text


@pytest.mark.asyncio
async def test_csrf_rejects_evil_origin():
    """(e) a POST with Origin: https://evil.example returns 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/auth/guest", headers={"Origin": "https://evil.example"})
        assert res.status_code == 403
        assert res.json() == {"detail": "Cross-site request blocked"}


@pytest.mark.asyncio
async def test_csrf_rejects_cookie_without_origin():
    """(f) a POST with the cookie and no Origin returns 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies={"nexus_session": "any-token"}
    ) as client:
        res = await client.post("/api/auth/guest")
        assert res.status_code == 403
        assert res.json() == {"detail": "Cross-site request blocked"}


@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_rate_db")
async def test_csrf_allows_bearer_without_origin_and_no_cookie():
    """(g) a POST with a Bearer header and no Origin and no cookie works."""
    user = _user()
    token, _ = create_access_token(session_claims(user))
    db = _UsersDb(user)
    app.dependency_overrides[get_db] = lambda: db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/auth/refresh",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
    finally:
        _ = app.dependency_overrides.pop(get_db, None)
