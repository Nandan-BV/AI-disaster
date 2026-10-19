import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.api.health import health_check


@pytest.mark.asyncio
async def test_health_reports_database_connected():
    database = SimpleNamespace(execute=AsyncMock())

    result = await health_check(database)

    assert result == {
        "status": "ok",
        "project": "RESQ-AI",
        "database": "connected",
    }


@pytest.mark.asyncio
async def test_health_reports_database_failure_as_degraded(caplog):
    database = SimpleNamespace(
        execute=AsyncMock(side_effect=SQLAlchemyError("database unavailable"))
    )

    result = await health_check(database)

    assert result.status_code == 503
    assert json.loads(result.body) == {
        "status": "degraded",
        "project": "RESQ-AI",
        "database": "disconnected",
    }
    assert "Database health check failed" in caplog.text
