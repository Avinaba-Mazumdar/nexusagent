import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.db.neon import neon_db
from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test the root endpoint returns app metadata."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "Welcome to NexusAgent" in data["message"]
        assert data["version"] == settings.VERSION
        assert data["health"] == "/api/health"
        assert "health_check" not in data


@pytest.mark.db
@pytest.mark.asyncio
async def test_health_endpoints():
    """Test /api/health endpoint with DB status verification."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["app_name"] == settings.APP_NAME
        assert data["version"] == settings.VERSION
        assert data["environment"] == settings.ENVIRONMENT
        assert data["database"]["status"] == "connected"
        assert "timestamp" in data
        assert "engine" in data["database"]
        assert "extensions" in data["database"]


@pytest.mark.asyncio
async def test_health_endpoint_unhealthy_when_db_disconnected(monkeypatch):
    """Test /api/health returns 503 and unhealthy status when pool is disconnected."""
    transport = ASGITransport(app=app)
    monkeypatch.setattr(neon_db, "pool", None)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"]["status"] == "disconnected"
        assert data["database"]["engine"] is None
        assert data["database"]["extensions"] == []


@pytest.mark.asyncio
async def test_cors_headers():
    """Test that configured CORS origins are accepted in options/get requests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        }
        response = await client.options("/api/health", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_health_hides_fingerprint_and_docs_in_production(monkeypatch):
    """SEC-11: production health omits DB version/extensions and API docs are not mounted."""
    from app.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        data = (await client.get("/api/health")).json()
    assert "engine" not in data["database"] and "extensions" not in data["database"]
    assert "environment" not in data and "version" not in data


@pytest.mark.asyncio
async def test_database_outage_returns_503(monkeypatch):
    """LOG-19: a missing pool becomes a 503, not an unhandled 500."""
    from app.core.auth import create_access_token

    monkeypatch.setattr(neon_db, "pool", None)
    token, _ = create_access_token({"sub": "00000000-0000-0000-0000-000000000001"})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 503
    assert res.headers["retry-after"] == "30"


def test_multiple_workers_are_refused_in_production_r2_sec_06(monkeypatch):
    import pytest

    from app.config import settings
    from app.main import ensure_single_worker

    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="exactly one worker"):
        ensure_single_worker()

    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    ensure_single_worker()

    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    ensure_single_worker()
