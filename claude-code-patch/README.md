# Claude Code CLI Source Patches

This directory contains the exact patches required to adapt the Claude Code CLI for local-first agent operation against an offline inference backend.

## Applied Patches

### 1. `01-base-url.patch`
- **Objective**: Enables `ANTHROPIC_BASE_URL` routing and unauthenticated local execution.
- **Details**:
  - Injects `baseURL` directly into the Anthropic SDK client options when `ANTHROPIC_BASE_URL` is set.
  - Automatically satisfies authentication in `src/utils/auth.ts` without requiring external OAuth or Anthropic cloud subscription tokens.

### 2. `02-small-fast-model.patch`
- **Objective**: Makes `ANTHROPIC_SMALL_FAST_MODEL` a mandatory configuration variable.
- **Details**:
  - Prevents the CLI from falling back to remote Haiku endpoints.
  - Guarantees all sub-agent tasks and background helper prompts run against the declared local model (e.g. `local-coding-agent`).

### 3. `03-retry-and-timeout.patch`
- **Objective**: Stabilizes execution for small parameter-scale local models.
- **Details**:
  - Enforces minimum 5 retries (`CLAUDE_CODE_RETRY_COUNT >= 5`).
  - Sets default timeout to 120 seconds (`API_TIMEOUT_MS = 120000`).

## How to Apply

```bash
cd claude-code-full
git apply ../claude-code-patch/01-base-url.patch
git apply ../claude-code-patch/02-small-fast-model.patch
git apply ../claude-code-patch/03-retry-and-timeout.patch
bun run build
```
