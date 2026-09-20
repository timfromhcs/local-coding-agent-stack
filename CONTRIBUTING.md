# Contributing to Local Coding Agent Stack

Thank you for your interest in contributing! This project is an autonomous, self-healing local coding agent stack that operates strictly without mocks or fake fixtures.

## Development Principles

1. **No Mocks in Integration Tests**: Every test runs against actual local inference, proxies, filesystem operations, and models.
2. **Self-Healing Verification**: Changes must pass all verification gates locally before submitting pull requests.
3. **Transparent Limitations**: Document hardware limits, memory usage, and performance benchmarks honestly.

## Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/timfromhcs/local-coding-agent-stack.git
   cd local-coding-agent-stack
   ```

2. Follow the setup guide in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

3. Run the verification test suite:
   ```bash
   pytest tests/ -v --cov=src
   ```

## Commit Guidelines

We enforce Conventional Commits:
- `feat:` for new capabilities
- `fix:` for bug fixes
- `test:` for test additions or hardening
- `docs:` for documentation updates
- `ci:` for CI/CD updates
