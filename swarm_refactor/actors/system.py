"""ActorSystem registry, router, and supervisor lifecycle manager."""

import asyncio
import logging
from typing import Dict, Optional
from .actor import Actor, ActorRef
from .envelope import Envelope

logger = logging.getLogger("swarm_refactor.system")

class ActorSystem:
    """Manages actor lifecycles, global address resolution, and message delivery."""

    def __init__(self, name: str = "swarm-system"):
        self.name = name
        self._actors: Dict[str, Actor] = {}
        self.dead_letters: asyncio.Queue[Envelope] = asyncio.Queue()

    async def spawn(self, actor: Actor) -> ActorRef:
        """Register and start an actor within the system."""
        actor_id = actor.actor_id
        if actor_id in self._actors:
            raise ValueError(f"Actor with ID '{actor_id}' already registered in system")
        
        actor.system = self
        self._actors[actor_id] = actor
        await actor.start()
        return actor.ref()

    def get_actor(self, actor_id: str) -> Optional[ActorRef]:
        """Look up an actor reference by ID."""
        actor = self._actors.get(actor_id)
        return actor.ref() if actor else None

    async def send(self, envelope: Envelope) -> bool:
        """Route an envelope to the recipient actor."""
        recipient = self.get_actor(envelope.recipient)
        if recipient:
            await recipient.tell(envelope)
            return True
        else:
            logger.warning(f"Message undeliverable to [{envelope.recipient}]. Routing to dead letters.")
            await self.dead_letters.put(envelope)
            return False

    async def shutdown(self) -> None:
        """Gracefully stop all actors in the cluster."""
        logger.info(f"Shutting down ActorSystem '{self.name}' ({len(self._actors)} actors)...")
        tasks = [actor.stop() for actor in self._actors.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._actors.clear()
        logger.info(f"ActorSystem '{self.name}' shutdown complete.")
