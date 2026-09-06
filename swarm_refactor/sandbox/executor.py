"""Isolated sandbox runner for validating candidate patches against test suites."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional
from .analyzer import TracebackAnalyzer
from ..schemas import CriticDiagnosis

class SandboxExecutor:
    """Executes test suites against code patches in an isolated ephemeral directory."""

    def __init__(self, timeout_sec: float = 6.0):
        self.timeout_sec = timeout_sec

    async def evaluate_patch(
        self,
        task_id: str,
        source_code: str,
        test_code: str,
        source_name: str = "candidate.py",
        test_name: str = "test_candidate.py",
    ) -> CriticDiagnosis:
        with tempfile.TemporaryDirectory(prefix="swarm_sandbox_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_file = tmp_path / source_name
            test_file = tmp_path / test_name

            # Write candidate code and test file
            source_file.write_text(source_code, encoding="utf-8")
            test_file.write_text(test_code, encoding="utf-8")

            # Execute test runner in subprocess using current python executable
            python_bin = sys.executable
            # We run with pytest or fallback to unittest if pytest not available
            cmd = [python_bin, "-m", "pytest", str(test_file), "-v", "--tb=short"]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(tmp_path),
                    env={**os.environ, "PYTHONPATH": str(tmp_path)},
                )

                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout_sec
                )

                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                combined = f"{stdout}\n{stderr}"
                exit_code = proc.returncode or 0
                passed = exit_code == 0

                summary, line, func, guidance = TracebackAnalyzer.parse_diagnostics(
                    combined, source_filename=source_name
                )

                return CriticDiagnosis(
                    task_id=task_id,
                    passed=passed,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    error_summary=summary,
                    culprit_line=line,
                    culprit_function=func,
                    constitutional_guidance=guidance,
                )

            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass

                return CriticDiagnosis(
                    task_id=task_id,
                    passed=False,
                    exit_code=-1,
                    stdout="",
                    stderr="Execution timed out (possible infinite recursion or dead-lock).",
                    error_summary="TimeoutError: Test execution exceeded time limit.",
                    culprit_line=None,
                    culprit_function=None,
                    constitutional_guidance="Algorithm stalled or entered infinite loop. Introduce termination guards and bounds checking.",
                )
            except Exception as e:
                return CriticDiagnosis(
                    task_id=task_id,
                    passed=False,
                    exit_code=-2,
                    stdout="",
                    stderr=str(e),
                    error_summary=f"SandboxError: {type(e).__name__} - {str(e)}",
                    culprit_line=None,
                    culprit_function=None,
                    constitutional_guidance="Execution environment failed to run tests.",
                )
