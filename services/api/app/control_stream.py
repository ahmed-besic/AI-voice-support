from __future__ import annotations

import asyncio
import json
from collections import defaultdict


class ControlStreamBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[str]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            self._subscribers[session_id].add(queue)
        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(session_id)
            if not subscribers:
                return
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(session_id, None)

    async def publish(self, session_id: str, event_type: str, payload: dict) -> None:
        message = _encode_sse(event_type, payload)
        async with self._lock:
            subscribers = list(self._subscribers.get(session_id, ()))
        for queue in subscribers:
            await queue.put(message)


def _encode_sse(event_type: str, payload: dict) -> str:
    return f'event: {event_type}\ndata: {json.dumps(payload)}\n\n'


control_stream_broker = ControlStreamBroker()
