import asyncio

import pytest

from appgpu.infrastructure import MessageBus


@pytest.mark.asyncio
async def test_message_bus_publish_subscribe():
    bus = MessageBus()
    received = []

    class Event:
        pass

    async def handler(event):
        received.append(event)

    bus.subscribe(Event, handler)

    async def runner():
        await bus.publish(Event())
        await asyncio.sleep(0.01)
        await bus.stop()

    task = asyncio.create_task(bus.start())
    await runner()
    await task

    assert len(received) == 1
