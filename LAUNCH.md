# 🚀 Viral Launch Kit for `swarm-refactor`

## 1. Hacker News (Show HN)
- **Title**: `Show HN: SwarmRefactor – Actor Model multi-agent framework for iterative code self-healing`
- **URL**: `https://github.com/nff747/swarm-refactor`
- **First Comment**:
```markdown
Hey HN,

Zero-shot LLM code generation notoriously fails on complex multi-file refactoring tasks.

SwarmRefactor implements an Actor-model orchestration framework (inspired by Erlang/Akka) where specialized agents collaborate in an iterative eval-and-correct loop:
- Manager Actor: Plans refactoring tasks and coordinates workers.
- Worker Actors: Query local LLMs (vLLM, Ollama) to synthesize candidate patches.
- Critic Actor: Executes unit tests in a hardened subprocess sandbox with static AST security filtering and POSIX rlimits (512MB RAM, 5s CPU cap).
- Traceback Analyzer: Parses stack traces, extracts culprit lines, and provides constitutional feedback for iterative convergence.

Repo: https://github.com/nff747/swarm-refactor
License: MIT
```

---

## 2. Twitter / X Post (Under 280 chars - no subscription needed)
```text
LLMs fail on multi-file refactors.

I built SwarmRefactor: Actor-model code self-healing.

- Erlang-style Actor orchestration
- Local LLMs (Ollama/vLLM)
- AST security gate + POSIX rlimits
- Auto test-eval loop (MIT)

https://github.com/nff747/swarm-refactor

#ai #python
```
