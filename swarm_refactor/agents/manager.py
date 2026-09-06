"""Manager Agent Actor: Supervises task delegation, evaluation pipelines, and convergence loops."""

import asyncio
import logging
from typing import Dict, Optional, List
from ..actors import Actor, Envelope
from .messages import RefactorTask, PatchProposal, CriticDiagnosis, TaskFinished

logger = logging.getLogger("swarm_refactor.manager")

class ManagerActor(Actor):
    """Supervisor agent coordinating the iterative refactoring and self-correction loop."""

    def __init__(self, actor_id: str, worker_id: str, critic_id: str):
        super().__init__(actor_id)
        self.worker_id = worker_id
        self.critic_id = critic_id
        self.active_tasks: Dict[str, RefactorTask] = {}
        self.diagnoses_history: Dict[str, List[CriticDiagnosis]] = {}
        self.latest_proposals: Dict[str, PatchProposal] = {}
        self.completion_events: Dict[str, asyncio.Event] = {}
        self.final_results: Dict[str, TaskFinished] = {}

    async def submit_task(self, task: RefactorTask) -> TaskFinished:
        """Entry point for clients submitting refactoring requests."""
        self.active_tasks[task.task_id] = task
        self.diagnoses_history[task.task_id] = []
        event = asyncio.Event()
        self.completion_events[task.task_id] = event

        logger.info(f"Manager [{self.actor_id}] initiating refactoring workflow for task '{task.task_id}'...")

        # Dispatch initial task to Worker
        await self.system.send(
            Envelope(
                sender=self.actor_id,
                recipient=self.worker_id,
                message_type="RefactorTask",
                payload=task,
                correlation_id=task.task_id,
            )
        )

        await event.wait()
        return self.final_results[task.task_id]

    async def receive(self, envelope: Envelope) -> None:
        task_id = envelope.correlation_id

        if envelope.message_type == "PatchProposal":
            proposal: PatchProposal = envelope.payload
            self.latest_proposals[task_id] = proposal
            task = self.active_tasks[task_id]

            logger.info(f"Manager [{self.actor_id}] received patch proposal from [{envelope.sender}] for task '{task_id}'. Dispatching to Critic...")

            # Forward to Critic for test evaluation
            await self.system.send(
                Envelope(
                    sender=self.actor_id,
                    recipient=self.critic_id,
                    message_type="EvaluatePatch",
                    payload={
                        "task_id": task_id,
                        "source_code": proposal.refactored_code,
                        "test_code": task.test_code,
                        "attempt": proposal.attempt,
                    },
                    correlation_id=task_id,
                )
            )

        elif envelope.message_type == "CriticDiagnosis":
            diagnosis: CriticDiagnosis = envelope.payload
            self.diagnoses_history[task_id].append(diagnosis)
            task = self.active_tasks[task_id]
            proposal = self.latest_proposals[task_id]

            if diagnosis.passed:
                logger.info(f"🎉 Manager [{self.actor_id}] CONVERGED: Task '{task_id}' verified successfully after {proposal.attempt} attempt(s)!")
                self.final_results[task_id] = TaskFinished(
                    task_id=task_id,
                    success=True,
                    final_code=proposal.refactored_code,
                    iterations=proposal.attempt,
                    diagnoses=self.diagnoses_history[task_id],
                )
                self.completion_events[task_id].set()

            elif proposal.attempt < task.max_attempts:
                next_attempt = proposal.attempt + 1
                logger.warning(
                    f"⚠️ Manager [{self.actor_id}] Test failed on attempt {proposal.attempt}/{task.max_attempts}. "
                    f"Feeding stack trace back to Worker for iteration {next_attempt}..."
                )

                # Re-dispatch with diagnostic trace back to Worker
                updated_task = task.model_copy(
                    update={
                        "attempt": next_attempt,
                        "prior_diagnosis": diagnosis,
                    }
                )
                self.active_tasks[task_id] = updated_task

                await self.system.send(
                    Envelope(
                        sender=self.actor_id,
                        recipient=self.worker_id,
                        message_type="RefactorTask",
                        payload=updated_task,
                        correlation_id=task_id,
                    )
                )

            else:
                logger.error(f"❌ Manager [{self.actor_id}] Task '{task_id}' exhausted maximum attempts ({task.max_attempts}). Halting.")
                self.final_results[task_id] = TaskFinished(
                    task_id=task_id,
                    success=False,
                    final_code=proposal.refactored_code,
                    iterations=proposal.attempt,
                    diagnoses=self.diagnoses_history[task_id],
                )
                self.completion_events[task_id].set()
