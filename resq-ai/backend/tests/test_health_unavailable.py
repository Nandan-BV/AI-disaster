import json
from unittest.mock import AsyncMock

import pytest

from app.api.health import health_check


@pytest.mark.asyncio
async def test_health_reports_database_connection_refused_as_degraded():
    db = AsyncMock()
    db.execute.side_effect = ConnectionRefusedError("database unavailable")

    response = await health_check(db)

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "degraded",
        "project": "RESQ-AI",
        "database": "disconnected",
        "copilot": "unknown",
    }
