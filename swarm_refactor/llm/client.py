"""LLM client interface supporting local Ollama, vLLM, and deterministic test backends."""

import re
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger("swarm_refactor.llm")

class LLMClient:
    """Client for querying local or remote LLM backends."""

    def __init__(
        self,
        provider: str = "mock",
        endpoint: Optional[str] = None,
        model: str = "deepseek-coder:6.7b",
        temperature: float = 0.2,
    ):
        self.provider = provider.lower()
        self.endpoint = endpoint
        self.model = model
        self.temperature = temperature

        if self.provider == "ollama" and not self.endpoint:
            self.endpoint = "http://localhost:11434/api/generate"
        elif self.provider == "vllm" and not self.endpoint:
            self.endpoint = "http://localhost:8000/v1/chat/completions"

    async def generate_code(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Dispatches prompt to configured inference backend."""
        if self.provider == "ollama":
            return await self._call_ollama(prompt, system_prompt)
        elif self.provider == "vllm":
            return await self._call_vllm(prompt, system_prompt)
        else:
            return self._mock_generate(prompt)

    async def _call_ollama(self, prompt: str, system_prompt: Optional[str]) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or "You are an elite principal software engineer.",
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return self._extract_code(data.get("response", ""))

    async def _call_vllm(self, prompt: str, system_prompt: Optional[str]) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            return self._extract_code(raw_text)

    def _extract_code(self, response: str) -> str:
        """Extracts python fenced code blocks from markdown."""
        code_blocks = re.findall(r"```(?:python)?\s*(.*?)\s*```", response, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()
        return response.strip()

    def _mock_generate(self, prompt: str) -> str:
        """
        Deterministic mock generator for offline CI/testing and local verification.
        Simulates the iterative debugging process:
        - Attempt 1: Produces refactored code with an edge-case bug.
        - Attempt 2: Analyzes the critic guidance in the prompt and resolves the bug.
        """
        is_reflection = any(keyword in prompt for keyword in ["Execution failed with", "Critic Diagnosis", "CRITIC FEEDBACK", "prior_diagnosis"])

        if "divide" in prompt:
            if is_reflection:
                return (
                    "def divide(a: float, b: float) -> float:\n"
                    "    \"\"\"Divide two numbers safely.\"\"\"\n"
                    "    if b == 0:\n"
                    "        return 0.0\n"
                    "    return a / b\n"
                )
            else:
                return (
                    "def divide(a: float, b: float) -> float:\n"
                    "    return a / b\n"
                )

        if is_reflection:
            # Reflection step: Produce fully corrected, optimized code
            return (
                "def calculate_stats(numbers: list[float]) -> dict[str, float]:\n"
                "    \"\"\"Calculates statistical summary with zero-division safety.\"\"\"\n"
                "    if not numbers:\n"
                "        return {\"mean\": 0.0, \"variance\": 0.0, \"count\": 0}\n"
                "    \n"
                "    n = len(numbers)\n"
                "    mean = sum(numbers) / n\n"
                "    variance = sum((x - mean) ** 2 for x in numbers) / n\n"
                "    return {\"mean\": mean, \"variance\": variance, \"count\": n}\n"
            )
        else:
            # Initial attempt: Has an unhandled zero-length edge case (triggers ZeroDivisionError in tests)
            return (
                "def calculate_stats(numbers: list[float]) -> dict[str, float]:\n"
                "    \"\"\"Calculates statistical summary with potential zero-division.\"\"\"\n"
                "    n = len(numbers)\n"
                "    # Flaw: misses empty list guard\n"
                "    mean = sum(numbers) / n\n"
                "    variance = sum((x - mean) ** 2 for x in numbers) / n\n"
                "    return {\"mean\": mean, \"variance\": variance, \"count\": n}\n"
            )
