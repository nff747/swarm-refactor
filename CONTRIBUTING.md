# Contributing to SwarmRefactor

Thank you for contributing to **SwarmRefactor**, an autonomous multi-agent refactoring framework based on the Actor Model and sandboxed test validation.

## Local Development

SwarmRefactor uses Python 3.10+ and [`uv`](https://github.com/astral-sh/uv) for fast dependency management.

```bash
uv sync
uv run pytest tests/
```

### Formatting & Linting

```bash
uv run ruff check .
uv run ruff format .
```

## Security Guidelines

When extending the execution sandbox:
- Never expose ambient host environment variables or filesystem access to the sandbox worker.
- All new code generation tools must respect the `ASTSecurityGate` restrictions and POSIX `rlimit` constraints.

## Contribution Workflow

1. Fork the repo and create a feature branch (`git checkout -b feat/my-feature`).
2. Implement your changes and add test cases to `tests/test_swarm.py`.
3. Verify test coverage:
   ```bash
   uv run pytest tests/ -v
   ```
4. Submit a Pull Request.

## License

By contributing to SwarmRefactor, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
