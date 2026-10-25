"""Priority-ordered asynchronous mailbox implementation for Swarm actors."""

import asyncio
from typing import Any, Tuple
from .envelope import Envelope

class PriorityMailbox:
    """Actor mailbox backing asynchronous queue ordered by envelope priority and arrival timestamp."""

    def __init__(self, maxsize: int = 1000):
        self.maxsize = maxsize
        self._queue: asyncio.PriorityQueue[Tuple[int, float, Envelope]] = asyncio.PriorityQueue(maxsize=maxsize)

    async def put(self, envelope: Envelope) -> None:
        """Enqueue envelope ordered by (priority, timestamp)."""
        item = (envelope.priority, envelope.timestamp, envelope)
        await self._queue.put(item)

    def put_nowait(self, envelope: Envelope) -> None:
        """Enqueue envelope immediately without waiting."""
        item = (envelope.priority, envelope.timestamp, envelope)
        self._queue.put_nowait(item)

    async def get(self) -> Envelope:
        """Dequeue the highest priority envelope."""
        _, _, envelope = await self._queue.get()
        return envelope

    def get_nowait(self) -> Envelope:
        """Dequeue the highest priority envelope immediately."""
        _, _, envelope = self._queue.get_nowait()
        return envelope

    def task_done(self) -> None:
        """Indicate that a formerly enqueued task is complete."""
        self._queue.task_done()

    def qsize(self) -> int:
        """Return the approximate size of the mailbox queue."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Return True if mailbox is empty."""
        return self._queue.empty()
