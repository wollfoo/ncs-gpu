"""Message bus asyncio cho kiến trúc hướng sự kiện."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import DefaultDict, List, Protocol


class EventHandler(Protocol):
    async def __call__(self, event: object) -> None: ...


class MessageBus:
    """Bus hỗ trợ publish/subscribe bất đồng bộ."""

    def __init__(self) -> None:
        self._subscribers: DefaultDict[type, List[EventHandler]] = defaultdict(list)
        self._queue: "asyncio.Queue[object]" = asyncio.Queue()
        self._running = False

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event: object) -> None:
        await self._queue.put(event)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        while self._running:
            event = await self._queue.get()
            handlers = self._subscribers.get(type(event), [])
            await asyncio.gather(*(handler(event) for handler in handlers))
            self._queue.task_done()

    async def stop(self) -> None:
        self._running = False
        await self._queue.put(object())
