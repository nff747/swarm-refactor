"""Actor base class, ActorRef, and supervisory lifecycle management."""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, Callable
from .envelope import Envelope

logger = logging.getLogger("swarm_refactor.actor")

class ActorState(Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    FAULTED = "FAULTED"
    STOPPED = "STOPPED"

class ActorRef:
    """Lightweight handle for addressing and dispatching messages to an Actor."""
    def __init__(self, actor_id: str, mailbox: asyncio.Queue):
        self.actor_id = actor_id
        self._mailbox = mailbox

    async def tell(self, envelope: Envelope) -> None:
        """Asynchronous fire-and-forget message dispatch."""
        await self._mailbox.put(envelope)

    def tell_nowait(self, envelope: Envelope) -> None:
        """Non-blocking message dispatch."""
        self._mailbox.put_nowait(envelope)

    async def ask(self, envelope: Envelope, timeout: float = 30.0) -> Any:
        """Request-response pattern with future resolution."""
        # Typically backed by a temporary response future
        raise NotImplementedError("Use message correlation pattern with tell for async coordination")

class Actor(ABC):
    """Base Actor implementation providing Erlang/Akka-style actor semantics."""

    def __init__(self, actor_id: str):
        self.actor_id = actor_id
        self.mailbox: asyncio.Queue[Envelope] = asyncio.Queue(maxsize=1000)
        self.state: ActorState = ActorState.CREATED
        self._loop_task: Optional[asyncio.Task] = None
        self.system: Optional["ActorSystem"] = None
        self.failure_count: int = 0
        self.max_restarts: int = 3

    def ref(self) -> ActorRef:
        return ActorRef(self.actor_id, self.mailbox)

    async def start(self) -> None:
        """Start the actor's asynchronous event loop."""
        self.state = ActorState.RUNNING
        self._loop_task = asyncio.create_task(self._run_loop())
        logger.debug(f"Actor [{self.actor_id}] started.")

    async def _run_loop(self) -> None:
        while self.state == ActorState.RUNNING:
            try:
                envelope = await self.mailbox.get()
                await self.receive(envelope)
                self.mailbox.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.failure_count += 1
                logger.error(f"Actor [{self.actor_id}] faulted during receive: {e}", exc_info=True)
                self.state = ActorState.FAULTED
                await self.handle_fault(e)
                if self.failure_count <= self.max_restarts:
                    logger.info(f"Restarting actor [{self.actor_id}] (attempt {self.failure_count}/{self.max_restarts})...")
                    self.state = ActorState.RUNNING
                else:
                    logger.critical(f"Actor [{self.actor_id}] exceeded max restarts. Halting.")
                    self.state = ActorState.STOPPED
                    break

    @abstractmethod
    async def receive(self, envelope: Envelope) -> None:
        """User-defined message handling routine."""
        pass

    async def handle_fault(self, exception: Exception) -> None:
        """Hook called when unhandled exception occurs in actor loop."""
        pass

    async def stop(self) -> None:
        """Gracefully stop the actor."""
        self.state = ActorState.STOPPED
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        logger.debug(f"Actor [{self.actor_id}] stopped.")
