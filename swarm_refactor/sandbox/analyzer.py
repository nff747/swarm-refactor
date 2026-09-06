"""Traceback and diagnostic analyzer for Python test failures."""

import re
from typing import Tuple, Optional

class TracebackAnalyzer:
    """Parses raw stderr and test runner output to extract precise failure causality."""

    @staticmethod
    def parse_diagnostics(output: str, source_filename: str = "candidate.py") -> Tuple[str, Optional[int], Optional[str], str]:
        """
        Parses output and returns:
        (error_summary, culprit_line, culprit_function, constitutional_guidance)
        """
        if "PASSED" in output and "FAILED" not in output and "ERROR" not in output:
            return ("All unit tests passed successfully.", None, None, "Code meets all assertions.")

        # 1. Look for Python exception types
        error_match = re.search(r"([A-Za-z_]+Error|AssertionError|Exception): (.+)", output)
        error_type = error_match.group(1) if error_match else "TestFailure"
        error_msg = error_match.group(2) if error_match else "Assertion mismatch"

        # 2. Extract line number and function inside candidate source
        line_match = re.findall(rf'File ".*{source_filename}", line (\d+), in (\w+)', output)
        culprit_line = None
        culprit_func = None
        if line_match:
            last_frame = line_match[-1]
            culprit_line = int(last_frame[0])
            culprit_func = last_frame[1]

        # 3. Check for failed assertions with values
        assertion_detail = ""
        diff_match = re.search(r"(AssertionError: .*|assert .* == .*)", output)
        if diff_match:
            assertion_detail = f" [Context: {diff_match.group(1)}]"

        summary = f"{error_type}: {error_msg}{assertion_detail}"

        # 4. Formulate prescriptive guidance for LLM self-correction
        guidance = (
            f"Execution failed with {error_type}. "
            f"Target function '{culprit_func or 'unknown'}' failed near line {culprit_line or 'N/A'}. "
            f"Details: {error_msg}. "
            "Please review the algorithmic edge cases and adjust the implementation to satisfy all test invariants."
        )

        return (summary, culprit_line, culprit_func, guidance)
