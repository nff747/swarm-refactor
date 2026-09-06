"""High-level Orchestrator interface for managing Actor cluster lifecycles."""

import uuid
from typing import Optional
from .actors import ActorSystem
from .llm import LLMClient
from .agents import ManagerActor, WorkerActor, CriticActor, RefactorTask, TaskFinished

class SwarmOrchestrator:
    """Entry point for initiating and executing multi-agent code refactoring swarms."""

    def __init__(
        self,
        provider: str = "mock",
        endpoint: Optional[str] = None,
        model: str = "deepseek-coder:6.7b",
        sandbox_timeout: float = 6.0,
    ):
        self.provider = provider
        self.endpoint = endpoint
        self.model = model
        self.sandbox_timeout = sandbox_timeout
        self.system = ActorSystem(name="swarm-refactor-cluster")
        self.llm_client = LLMClient(
            provider=provider, endpoint=endpoint, model=model
        )

    async def refactor_code(
        self,
        source_code: str,
        test_code: str,
        objective: str = "Refactor code to fix edge-case bugs and optimize performance.",
        file_path: str = "module.py",
        max_attempts: int = 5,
    ) -> TaskFinished:
        """Launches the Actor system and executes iterative refactoring until convergence."""
        worker = WorkerActor(actor_id="worker-agent-1", llm_client=self.llm_client)
        critic = CriticActor(actor_id="critic-agent-1", timeout_sec=self.sandbox_timeout)
        manager = ManagerActor(
            actor_id="manager-agent-1",
            worker_id="worker-agent-1",
            critic_id="critic-agent-1",
        )

        # Register actors into cluster
        await self.system.spawn(worker)
        await self.system.spawn(critic)
        await self.system.spawn(manager)

        task = RefactorTask(
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            file_path=file_path,
            source_code=source_code,
            test_code=test_code,
            objective=objective,
            max_attempts=max_attempts,
        )

        try:
            result = await manager.submit_task(task)
            return result
        finally:
            await self.system.shutdown()
