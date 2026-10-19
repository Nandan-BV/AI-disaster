from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.config import Settings
from app.core.security import create_access_token
from app.database import get_db
from app.main import app
from app.schemas.user import UserCreate
from app.models.user import UserRole


def test_production_requires_a_strong_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", JWT_SECRET_KEY="short")


def test_registration_rejects_passwords_exceeding_bcrypt_byte_limit():
    with pytest.raises(ValidationError):
        UserCreate(username="analyst", password="測" * 25)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDatabase:
    def __init__(self, user, allocation):
        self.results = [FakeResult(user), FakeResult(allocation)]
        self.execute_count = 0

    async def execute(self, _query):
        result = self.results[self.execute_count]
        self.execute_count += 1
        return result

    async def commit(self):
        pass

    async def refresh(self, _instance):
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "token", "expected_status"),
    [
        (UserRole.DISPATCHER, None, 401),
        (UserRole.ANALYST, "valid", 403),
        (UserRole.DISPATCHER, "valid", 200),
    ],
)
async def test_allocation_status_requires_operator_role(
    role, token, expected_status
):
    user_id = uuid4()
    user = SimpleNamespace(id=user_id, role=role, is_active=True)
    allocation = SimpleNamespace(
        id=uuid4(),
        incident_id=uuid4(),
        optimization_result_id=uuid4(),
        resource_id=uuid4(),
        resource_type="ambulance",
        distance_meters=100.0,
        assignment_score=0.9,
        assignment_reason="nearest available resource",
        status="recommended",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    database = FakeDatabase(user, allocation)

    async def override_get_db():
        yield database

    app.dependency_overrides[get_db] = override_get_db
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {create_access_token(user_id)}"

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.patch(
                f"/api/v1/incidents/resource-allocations/{allocation.id}/status",
                json={"status": "approved"},
                headers=headers,
            )
        assert response.status_code == expected_status
    finally:
        app.dependency_overrides.clear()
