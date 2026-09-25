---
name: cross-llm-codex
description: >-
  Run a multi-slice cross-LLM build with Claude as lead and an explicitly
  selected Codex CLI model as the headless executor in isolated Git worktrees.
---
{{BANNER}}

# Cross-LLM Delivery — Claude host, Codex executor

Claude authors slice contracts and acceptance tests, reviews every candidate,
and integrates only accepted work. The vendored driver runs from `scripts/`;
it requires an exact `--executor codex:<model-id>@<effort>` for dispatch.
There is no default Codex model or verified subscription entitlement.

Run from this skill directory with absolute plan and repository paths:

```bash
python scripts/run_delivery.py <plan.md> --repo <dir> --dry-run --json
python scripts/run_delivery.py <plan.md> --repo <dir> --step --executor codex:<model-id>@<effort> --validation-policy allow --json
python scripts/run_delivery.py <plan.md> --repo <dir> --integrate --integration-tests <selector> --json
```

Obtain the exact model and reasoning effort from the user. Keep that choice for
the build; do not silently substitute. A catalog listing does not prove live
access. Validation dispatches spend tokens, and USD cost may be unknown; apply
the user's authorization and CLD's admission and unknown-usage policies.

{{PROVIDER_FRAGMENT}}

{{SETUP}}

For gate meanings and recovery, read `references/delivery-core.md`. CLD judges
the real Git diff and acceptance tests, not the executor's final prose.
