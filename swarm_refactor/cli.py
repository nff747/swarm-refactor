"""Command-Line Interface (CLI) for SwarmRefactor."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from .orchestrator import SwarmOrchestrator

DEMO_SOURCE_CODE = """# Flawed implementation: Fails on empty input or non-numeric types
def calculate_stats(numbers):
    n = len(numbers)
    mean = sum(numbers) / n
    variance = sum((x - mean) ** 2 for x in numbers) / n
    return {"mean": mean, "variance": variance, "count": n}
"""

DEMO_TEST_CODE = """import pytest
from candidate import calculate_stats

def test_nominal_stats():
    res = calculate_stats([1.0, 2.0, 3.0, 4.0, 5.0])
    assert res["count"] == 5
    assert res["mean"] == 3.0
    assert pytest.approx(res["variance"], 0.01) == 2.0

def test_empty_list_edge_case():
    # Should not raise ZeroDivisionError!
    res = calculate_stats([])
    assert res["count"] == 0
    assert res["mean"] == 0.0
    assert res["variance"] == 0.0
"""

def main():
    parser = argparse.ArgumentParser(description="SwarmRefactor: Autonomous Multi-Agent Code Refactoring")
    parser.add_argument("--demo", action="store_true", help="Run interactive self-correcting multi-agent demo")
    parser.add_argument("--file", "-f", type=str, help="Path to python file to refactor")
    parser.add_argument("--tests", "-t", type=str, help="Path to test file to validate against")
    parser.add_argument("--objective", "-o", type=str, default="Fix edge cases and optimize code safety", help="Goal")
    parser.add_argument("--provider", "-p", type=str, default="mock", choices=["mock", "ollama", "vllm"], help="LLM backend")
    parser.add_argument("--model", "-m", type=str, default="deepseek-coder:6.7b", help="Model name")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    print("=================================================================")
    print("  SWARM-REFACTOR // AUTONOMOUS MULTI-AGENT ACTOR CLUSTER")
    print("=================================================================")
    print(f"  Backend Provider : {args.provider}")
    print(f"  Target LLM Model : {args.model}")
    print("-----------------------------------------------------------------")

    if args.demo or not args.file:
        source_code = DEMO_SOURCE_CODE
        test_code = DEMO_TEST_CODE
        print("\n[INFO] Running built-in self-correcting demonstration...")
    else:
        source_code = Path(args.file).read_text(encoding="utf-8")
        test_code = Path(args.tests).read_text(encoding="utf-8") if args.tests else ""

    async def _run():
        orchestrator = SwarmOrchestrator(
            provider=args.provider,
            model=args.model,
        )
        result = await orchestrator.refactor_code(
            source_code=source_code,
            test_code=test_code,
            objective=args.objective,
        )

        print("\n=================================================================")
        print(f"  WORKFLOW COMPLETE // SUCCESS: {result.success.upper() if isinstance(result.success, str) else result.success}")
        print(f"  Total Iterations: {result.iterations}")
        print("=================================================================")
        print("\n### FINAL APPROVED REFACTORED CODE:")
        print(result.final_code)

        if not result.success:
            sys.exit(1)

    asyncio.run(_run())

if __name__ == "__main__":
    main()
