"""Context Window Compressor and Episodic Refactoring Memory."""

import ast
import difflib
from typing import Dict, List, Optional

class ContextCompressor:
    """Compresses large codebase contexts to fit within tight LLM context windows."""

    @staticmethod
    def extract_ast_skeleton(code: str) -> str:
        """Parses Python AST and returns a skeletal signature view of classes and functions."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code[:500] + "\n# ... [Syntax truncated]"

        skeleton_lines = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                args = [a.arg for a in node.args.args]
                ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                skeleton_lines.append(f"def {node.name}({', '.join(args)}){ret}: ...")
            elif isinstance(node, ast.ClassDef):
                skeleton_lines.append(f"class {node.name}:")
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in item.args.args]
                        ret = f" -> {ast.unparse(item.returns)}" if item.returns else ""
                        skeleton_lines.append(f"    def {item.name}({', '.join(args)}){ret}: ...")
        
        return "\n".join(skeleton_lines) if skeleton_lines else code

    @staticmethod
    def compute_diff(original: str, modified: str, filename: str = "target.py") -> str:
        """Computes a clean unified diff between two code snapshots."""
        orig_lines = original.splitlines(keepends=True)
        mod_lines = modified.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
        return "".join(diff)

class EpisodicMemory:
    """Stores successful diagnostic-to-patch patterns for few-shot in-context learning."""

    def __init__(self):
        self._memory: List[Dict[str, str]] = []

    def record_success(self, error_type: str, failing_code: str, passing_code: str, guidance: str):
        self._memory.append({
            "error_type": error_type,
            "guidance": guidance,
            "diff": ContextCompressor.compute_diff(failing_code, passing_code),
        })

    def find_relevant_episodes(self, error_type: str, limit: int = 2) -> List[Dict[str, str]]:
        """Retrieve historical episodes matching the error category."""
        return [ep for ep in self._memory if ep["error_type"].lower() in error_type.lower()][:limit]
