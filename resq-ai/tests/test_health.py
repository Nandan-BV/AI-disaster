import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api.health import health_check
from app.config import settings


@pytest.mark.asyncio
async def test_health_reports_database_connected(monkeypatch):
    monkeypatch.setattr(settings, "COPILOT_PROVIDER", "mock")
    database = SimpleNamespace(execute=AsyncMock())

    result = await health_check(database)

    assert result == {
        "status": "ok",
        "project": "RESQ-AI",
        "database": "connected",
        "copilot": "not_required",
    }


@pytest.mark.asyncio
async def test_health_reports_database_failure_as_degraded(caplog, monkeypatch):
    monkeypatch.setattr(settings, "COPILOT_PROVIDER", "mock")
    database = SimpleNamespace(
        execute=AsyncMock(side_effect=SQLAlchemyError("database unavailable"))
    )

    result = await health_check(database)

    assert result.status_code == 503
    assert json.loads(result.body) == {
        "status": "degraded",
        "project": "RESQ-AI",
        "database": "disconnected",
        "copilot": "unknown",
    }
    assert "Database health check failed" in caplog.text


@pytest.mark.asyncio
async def test_health_marks_optional_copilot_failure_as_degraded(monkeypatch):
    from app.api import health

    database = SimpleNamespace(execute=AsyncMock())
    client = SimpleNamespace(health_check=AsyncMock(return_value=False))
    monkeypatch.setattr(settings, "COPILOT_PROVIDER", "openai_compatible")
    monkeypatch.setattr(health, "get_llm_client", lambda: client)

    result = await health_check(database)

    assert result == {
        "status": "degraded",
        "project": "RESQ-AI",
        "database": "connected",
        "copilot": "unavailable",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "database_error",
    [
        OperationalError("SELECT 1", {}, ConnectionError("connection refused")),
        ConnectionRefusedError("connection refused"),
    ],
    ids=["sqlalchemy-operational-error", "connection-refused-error"],
)
async def test_database_connection_failure_returns_service_unavailable(database_error):
    from httpx import ASGITransport, AsyncClient
    from app.database import get_db
    from app.main import app

    database = SimpleNamespace(execute=AsyncMock(side_effect=database_error))

    async def override_database():
        yield database

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_database
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/events")
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous

    assert response.status_code == 503
    assert response.json() == {"detail": "Database service is unavailable."}
