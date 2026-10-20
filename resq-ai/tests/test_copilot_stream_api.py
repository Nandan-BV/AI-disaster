from unittest.mock import patch

from fastapi.testclient import TestClient

from app.ai.llm.base import Message
from app.ai.llm.openai_compatible import OpenAICompatibleClient
from app.database import get_db
from app.main import app
from app.core.security import get_current_user


def test_copilot_stream_endpoint_emits_sse_events():
    async def override_db():
        yield object()

    async def answer_stream(**_kwargs):
        yield {"type": "token", "token": "Hello "}
        yield {"type": "token", "token": "operator"}
        yield {"type": "done", "sources": [], "tools_used": []}

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: object()
    try:
        with patch("app.api.copilot.CopilotService") as service_factory:
            service_factory.return_value.answer_stream = answer_stream
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/copilot/sessions/demo-session/chat/stream",
                    json={"message": "What is happening?"},
                )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert 'event: token\r\ndata: {"token": "Hello "}' in response.text
        assert 'event: done\r\ndata: {"sources": [], "tools_used": []}' in response.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_normalized_tool_calls_are_serialized_for_follow_up_generation():
    messages = [
        Message(
            role="assistant",
            content="",
            tool_calls=[
                {"id": "call_1", "name": "get_incident", "arguments": "{}"}
            ],
        ),
        Message(role="tool", content="incident data", tool_call_id="call_1"),
    ]

    serialized = OpenAICompatibleClient._serialize(messages)

    assert serialized[0]["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_incident", "arguments": "{}"},
        }
    ]
    assert serialized[1]["tool_call_id"] == "call_1"
