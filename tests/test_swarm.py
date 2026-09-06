"""Comprehensive test suite for the SwarmRefactor multi-agent framework."""

import pytest
import asyncio
from swarm_refactor.actors.envelope import Envelope
from swarm_refactor.actors.actor import Actor, ActorState
from swarm_refactor.actors.system import ActorSystem
from swarm_refactor.sandbox.analyzer import TracebackAnalyzer
from swarm_refactor.sandbox.executor import SandboxExecutor
from swarm_refactor.memory.context import ContextCompressor, EpisodicMemory
from swarm_refactor.orchestrator import SwarmOrchestrator
from swarm_refactor.schemas import RefactorTask, PatchProposal, CriticDiagnosis


class EchoActor(Actor):
    """Simple test actor that records received messages."""

    def __init__(self, actor_id: str):
        super().__init__(actor_id)
        self.received = []

    async def receive(self, envelope: Envelope) -> None:
        self.received.append(envelope.payload)


@pytest.mark.asyncio
async def test_actor_lifecycle_and_messaging():
    system = ActorSystem(name="test-system")
    actor = EchoActor("echo-1")
    ref = await system.spawn(actor)

    assert ref.actor_id == "echo-1"
    assert actor.state == ActorState.RUNNING

    envelope = Envelope(
        sender="tester",
        recipient="echo-1",
        message_type="str",
        payload="hello world",
    )
    await ref.tell(envelope)
    await asyncio.sleep(0.05)

    assert len(actor.received) == 1
    assert actor.received[0] == "hello world"

    await system.shutdown()
    assert actor.state == ActorState.STOPPED


@pytest.mark.asyncio
async def test_dead_letters_routing():
    system = ActorSystem(name="dead-letters-system")
    envelope = Envelope(
        sender="tester",
        recipient="non-existent-actor",
        message_type="str",
        payload="lost message",
    )
    await system.send(envelope)
    assert system.dead_letters.qsize() == 1
    item = system.dead_letters.get_nowait()
    assert item.payload == "lost message"
    await system.shutdown()


def test_traceback_analyzer_extraction():
    fake_traceback = """
Traceback (most recent call last):
  File "/tmp/test_runner.py", line 25, in <module>
    test_func()
  File "/tmp/test_runner.py", line 18, in test_func
    res = divide(10, 0)
  File "/tmp/candidate.py", line 4, in divide
    return a / b
ZeroDivisionError: division by zero
"""
    summary, culprit_line, culprit_func, guidance = TracebackAnalyzer.parse_diagnostics(fake_traceback)
    assert "ZeroDivisionError" in summary
    assert culprit_line == 4
    assert culprit_func == "divide"
    assert "division by zero" in summary
    assert "ZeroDivisionError" in guidance


def test_context_compressor_ast_skeleton():
    sample_code = '''
"""Module docstring."""
import math

GLOBAL_CONST = 42

def add(a: int, b: int) -> int:
    """Add two numbers."""
    c = a + b
    return c

class Calculator:
    """A calculator class."""
    def multiply(self, x: float, y: float) -> float:
        return x * y
'''
    skeleton = ContextCompressor.extract_ast_skeleton(sample_code)
    assert "def add(a, b) -> int: ..." in skeleton
    assert "class Calculator:" in skeleton
    assert "def multiply(self, x, y) -> float: ..." in skeleton
    assert "c = a + b" not in skeleton


def test_context_compressor_unified_diff():
    old = "def foo():\n    return 1\n"
    new = "def foo():\n    return 2\n"
    diff = ContextCompressor.compute_diff(old, new)
    assert "-def foo():" in diff or "-    return 1" in diff
    assert "+    return 2" in diff


def test_episodic_memory():
    memory = EpisodicMemory()
    memory.record_success(
        error_type="IndexError",
        failing_code="return arr[10]",
        passing_code="if len(arr) > 10: return arr[10]",
        guidance="Check bounds before indexing",
    )
    matches = memory.find_relevant_episodes("IndexError")
    assert len(matches) == 1
    assert matches[0]["guidance"] == "Check bounds before indexing"
    assert "diff" in matches[0]


@pytest.mark.asyncio
async def test_sandbox_executor_passing_and_failing():
    executor = SandboxExecutor(timeout_sec=5.0)

    # Valid code that passes
    source_pass = "def add(a, b):\n    return a + b\n"
    test_pass = "from candidate import add\ndef test_add():\n    assert add(2, 3) == 5\n"
    res_pass = await executor.evaluate_patch("t-1", source_pass, test_pass)
    assert res_pass.passed is True
    assert res_pass.exit_code == 0

    # Flawed code that fails
    source_fail = "def add(a, b):\n    return a - b\n"
    test_fail = "from candidate import add\ndef test_add():\n    assert add(2, 3) == 5\n"
    res_fail = await executor.evaluate_patch("t-2", source_fail, test_fail)
    assert res_fail.passed is False
    assert res_fail.exit_code != 0
    assert "AssertionError" in res_fail.stderr or "assert" in res_fail.stdout or "FAILED" in res_fail.stdout


@pytest.mark.asyncio
async def test_swarm_orchestrator_convergence():
    orchestrator = SwarmOrchestrator(provider="mock")

    flawed_code = "def divide(a, b):\n    return a / b\n"
    test_suite = """
from candidate import divide
def test_valid():
    assert divide(10, 2) == 5
def test_zero():
    # Should handle zero divisor safely
    assert divide(10, 0) == 0.0
"""
    result = await orchestrator.refactor_code(
        source_code=flawed_code,
        test_code=test_suite,
        objective="Fix zero division error",
        max_attempts=3,
    )

    assert result.success is True
    assert result.iterations == 2
    assert "return 0.0" in result.final_code or "b == 0" in result.final_code
