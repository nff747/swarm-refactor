"""Typed message protocols for Manager, Worker, and Critic agents."""

from ..schemas import CriticDiagnosis, RefactorTask, PatchProposal, TaskFinished

__all__ = [
    "CriticDiagnosis",
    "RefactorTask",
    "PatchProposal",
    "TaskFinished",
]
