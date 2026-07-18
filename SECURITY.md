# Security Policy

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** for this repository (Security tab →
"Report a vulnerability"). It's enabled and goes directly to the maintainer without public
disclosure. Please do not open a public issue for security problems.

## Scope worth knowing about

`cld` dispatches work to executor CLIs with write access to an isolated git worktree of your
repo, and judges results by running that repo's tests. Relevant boundaries:

- Executors run with `--dangerously-skip-permissions`-style flags **inside a throwaway
  worktree**; accepted work is only merged after the diff rule + real test run pass.
- The engine itself has **no required third-party runtime dependencies** and makes no network
  calls of its own; network access happens inside the executor CLIs you install and the
  opt-in OTLP telemetry export.
- Rejected work is preserved locally as patches under `.cld/` — treat that directory as
  scratch containing model-generated code.

## Supported versions

The latest release (and `main`) receive fixes. There are no long-term support branches.
