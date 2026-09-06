"""Critic Agent Actor: Evaluates patches in an isolated sandbox and produces diagnostic feedback."""

import logging
from ..actors import Actor, Envelope
from ..sandbox.executor import SandboxExecutor
from .messages import PatchProposal, CriticDiagnosis

logger = logging.getLogger("swarm_refactor.critic")

class CriticActor(Actor):
    """Specialized evaluation agent that executes test suites against patch candidates."""

    def __init__(self, actor_id: str, timeout_sec: float = 6.0):
        super().__init__(actor_id)
        self.executor = SandboxExecutor(timeout_sec=timeout_sec)

    async def receive(self, envelope: Envelope) -> None:
        if envelope.message_type == "EvaluatePatch":
            payload = envelope.payload
            task_id = payload["task_id"]
            source_code = payload["source_code"]
            test_code = payload["test_code"]
            attempt = payload.get("attempt", 1)

            logger.info(f"Critic [{self.actor_id}] executing sandbox verification for task '{task_id}' (attempt {attempt})...")

            diagnosis: CriticDiagnosis = await self.executor.evaluate_patch(
                task_id=task_id,
                source_code=source_code,
                test_code=test_code,
            )

            status_str = "PASSED" if diagnosis.passed else "FAILED"
            logger.info(f"Critic [{self.actor_id}] result for task '{task_id}': {status_str} (Exit: {diagnosis.exit_code})")

            # Route diagnosis back to Manager
            await self.system.send(
                Envelope(
                    sender=self.actor_id,
                    recipient=envelope.sender,
                    message_type="CriticDiagnosis",
                    payload=diagnosis,
                    correlation_id=task_id,
                )
            )
        else:
            logger.warning(f"Critic [{self.actor_id}] received unhandled message '{envelope.message_type}'")
