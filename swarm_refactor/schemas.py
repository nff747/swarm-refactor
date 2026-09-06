"""Shared domain models and message schemas for the SwarmRefactor framework."""

from typing import Optional, List
from pydantic import BaseModel, Field


class CriticDiagnosis(BaseModel):
    """Evaluation verdict produced by the Critic agent after running unit tests in sandbox."""
    task_id: str
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    error_summary: str
    culprit_line: Optional[int] = None
    culprit_function: Optional[str] = None
    constitutional_guidance: str


class RefactorTask(BaseModel):
    """Specification of a codebase refactoring assignment."""
    task_id: str
    file_path: str
    source_code: str
    test_code: str
    objective: str
    attempt: int = 1
    max_attempts: int = 5
    prior_diagnosis: Optional[CriticDiagnosis] = None


class PatchProposal(BaseModel):
    """Refactored code candidate emitted by a Worker agent."""
    task_id: str
    worker_id: str
    refactored_code: str
    explanation: str
    diff: str
    attempt: int


class TaskFinished(BaseModel):
    """Final resolution reported by the Manager upon convergence or max iteration limit."""
    task_id: str
    success: bool
    final_code: str
    iterations: int
    diagnoses: List[CriticDiagnosis] = Field(default_factory=list)
