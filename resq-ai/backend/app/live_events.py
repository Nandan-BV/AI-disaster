import logging
from typing import Any, Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class EventConnectionManager:
    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        disconnected = []
        for websocket in tuple(self._connections):
            try:
                await websocket.send_json(message)
            except (OSError, RuntimeError, WebSocketDisconnect):
                logger.warning("Removing a failed live-event WebSocket connection.")
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket)


event_connections = EventConnectionManager()
