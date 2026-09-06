"""Worker Agent Actor: Generates and iteratively refactors code patches using LLMs."""

import logging
from ..actors import Actor, Envelope
from ..llm import LLMClient
from ..memory import ContextCompressor
from .messages import RefactorTask, PatchProposal

logger = logging.getLogger("swarm_refactor.worker")

class WorkerActor(Actor):
    """Specialized worker agent that translates tasks and diagnostic errors into code patches."""

    def __init__(self, actor_id: str, llm_client: LLMClient):
        super().__init__(actor_id)
        self.llm = llm_client

    async def receive(self, envelope: Envelope) -> None:
        if envelope.message_type == "RefactorTask":
            task: RefactorTask = envelope.payload
            await self._handle_refactor_task(task, envelope.sender)
        else:
            logger.warning(f"Worker [{self.actor_id}] received unhandled message type '{envelope.message_type}'")

    async def _handle_refactor_task(self, task: RefactorTask, manager_id: str) -> None:
        logger.info(f"Worker [{self.actor_id}] processing task '{task.task_id}' (attempt {task.attempt}/{task.max_attempts})...")

        # Build prompt incorporating task objective, current code, and any prior critic failure diagnostics
        prompt_parts = [
            f"### OBJECTIVE:\n{task.objective}\n",
            f"### SOURCE FILE ({task.file_path}):\n```python\n{task.source_code}\n```\n",
            f"### TEST SUITE:\n```python\n{task.test_code}\n```\n",
        ]

        if task.prior_diagnosis and not task.prior_diagnosis.passed:
            diag = task.prior_diagnosis
            prompt_parts.append(
                "### CRITIC FEEDBACK & FAILURE DIAGNOSIS (PRIOR ATTEMPT):\n"
                f"- Error Summary: {diag.error_summary}\n"
                f"- Culprit Function: {diag.culprit_function or 'unknown'}\n"
                f"- Culprit Line: {diag.culprit_line or 'unknown'}\n"
                f"- Constitutional Guidance: {diag.constitutional_guidance}\n"
                f"- Traceback Stderr:\n{diag.stderr}\n\n"
                "CRITICAL: Correct the code to address the exact failure above while preserving all original signatures."
            )

        prompt = "\n".join(prompt_parts)
        system_prompt = (
            "You are an elite code refactoring specialist. Return ONLY the complete refactored Python code "
            "wrapped in ```python ... ``` without extraneous conversation."
        )

        refactored = await self.llm.generate_code(prompt, system_prompt)
        diff = ContextCompressor.compute_diff(task.source_code, refactored, filename=task.file_path)

        proposal = PatchProposal(
            task_id=task.task_id,
            worker_id=self.actor_id,
            refactored_code=refactored,
            explanation=f"Refactoring iteration {task.attempt} addressing test constraints.",
            diff=diff,
            attempt=task.attempt,
        )

        # Dispatch proposal back to manager
        await self.system.send(
            Envelope(
                sender=self.actor_id,
                recipient=manager_id,
                message_type="PatchProposal",
                payload=proposal,
                correlation_id=task.task_id,
            )
        )
