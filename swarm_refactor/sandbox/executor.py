"""Isolated sandbox runner for validating candidate patches against test suites with strict security guarantees."""

import ast
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional
from .analyzer import TracebackAnalyzer
from ..schemas import CriticDiagnosis


class SecurityViolationError(Exception):
    """Raised when candidate code fails AST security static analysis."""
    pass


class ASTSecurityGate(ast.NodeVisitor):
    """Static AST analyzer that rejects malicious or hazardous patterns prior to execution."""

    BLOCKED_MODULES = {
        "subprocess",
        "shutil",
        "socket",
        "pty",
        "posix",
        "ctypes",
        "urllib",
        "http",
        "requests",
        "httpx",
        "asyncio.subprocess",
        "multiprocessing",
        "paramiko",
    }

    BLOCKED_BUILTINS = {
        "eval",
        "exec",
        "__import__",
        "compile",
    }

    BLOCKED_OS_ATTRS = {
        "system",
        "popen",
        "spawn",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "fork",
        "forkpty",
        "kill",
        "killpg",
        "remove",
        "unlink",
        "rmdir",
    }

    def __init__(self):
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_mod = alias.name.split(".")[0]
            if root_mod in self.BLOCKED_MODULES or alias.name in self.BLOCKED_MODULES:
                self.violations.append(f"Disallowed import '{alias.name}' at line {node.lineno}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root_mod = node.module.split(".")[0]
            if root_mod in self.BLOCKED_MODULES or node.module in self.BLOCKED_MODULES:
                self.violations.append(f"Disallowed from-import '{node.module}' at line {node.lineno}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct builtin calls (e.g. eval, exec, __import__)
        if isinstance(node.func, ast.Name):
            if node.func.id in self.BLOCKED_BUILTINS:
                self.violations.append(f"Prohibited builtin invocation '{node.func.id}()' at line {node.lineno}")
        # Check os.<blocked> calls
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                if node.func.attr in self.BLOCKED_OS_ATTRS:
                    self.violations.append(f"Prohibited os system call 'os.{node.func.attr}()' at line {node.lineno}")
        self.generic_visit(node)


def _set_posix_resource_limits() -> None:
    """Configures process resource limits inside the subprocess fork."""
    try:
        import resource
        # 512 MB virtual memory limit (address space)
        mem_limit = 512 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
        # 5 seconds max CPU time
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        # 10 MB file size limit
        fsize_limit = 10 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_limit, fsize_limit))
        # Disable core dumps
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ImportError, ValueError, OSError):
        pass


class SandboxExecutor:
    """Executes test suites against code patches in an isolated ephemeral directory with strict security sandboxing."""

    def __init__(self, timeout_sec: float = 6.0):
        self.timeout_sec = timeout_sec

    def validate_code_security(self, code: str, filename: str) -> Optional[str]:
        """Performs static analysis AST check. Returns error message if violation found, else None."""
        try:
            tree = ast.parse(code, filename=filename)
        except SyntaxError as e:
            return f"SyntaxError in {filename}: {e}"

        checker = ASTSecurityGate()
        checker.visit(tree)
        if checker.violations:
            return "; ".join(checker.violations)
        return None

    async def evaluate_patch(
        self,
        task_id: str,
        source_code: str,
        test_code: str,
        source_name: str = "candidate.py",
        test_name: str = "test_candidate.py",
    ) -> CriticDiagnosis:
        # Pre-execution static security gate
        sec_err = self.validate_code_security(source_code, source_name)
        if sec_err:
            return CriticDiagnosis(
                task_id=task_id,
                passed=False,
                exit_code=-3,
                stdout="",
                stderr=f"SecurityViolation: {sec_err}",
                error_summary="SecurityPolicyViolation: Disallowed API or dangerous module access detected.",
                culprit_line=None,
                culprit_function=None,
                constitutional_guidance="Security policy violation. Disallowed APIs (e.g., subprocess, socket, eval, os mutation) must not be used.",
            )

        with tempfile.TemporaryDirectory(prefix="swarm_sandbox_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_file = tmp_path / source_name
            test_file = tmp_path / test_name

            # Write candidate code and test file
            source_file.write_text(source_code, encoding="utf-8")
            test_file.write_text(test_code, encoding="utf-8")

            # Execute test runner in subprocess using current python executable
            python_bin = sys.executable
            cmd = [python_bin, "-m", "pytest", str(test_file), "-v", "--tb=short"]

            # Sanitized execution environment: Never leak host env vars (API keys, secrets, tokens)
            sanitized_env = {
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                "PYTHONPATH": str(tmp_path),
                "TEMP": str(tmp_path),
                "TMPDIR": str(tmp_path),
                "LANG": os.environ.get("LANG", "en_US.UTF-8"),
                "LC_ALL": os.environ.get("LC_ALL", "en_US.UTF-8"),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            if "VIRTUAL_ENV" in os.environ:
                sanitized_env["VIRTUAL_ENV"] = os.environ["VIRTUAL_ENV"]

            try:
                # Use preexec_fn on POSIX systems to enforce rlimits
                preexec = _set_posix_resource_limits if os.name == "posix" else None

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(tmp_path),
                    env=sanitized_env,
                    preexec_fn=preexec,
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
