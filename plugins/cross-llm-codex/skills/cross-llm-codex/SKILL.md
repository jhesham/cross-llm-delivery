---
name: cross-llm-codex
description: >-
  Run a multi-slice cross-LLM build with Claude as lead and an explicitly
  selected Codex CLI model as the headless executor in isolated Git worktrees.
---
<!-- GENERATED from cross-llm-delivery (provider: codex, v0.2.0) - do not edit here; edit the monorepo source. -->

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

## Codex CLI executor

Choose an exact Codex CLI model ID and optional supported effort for every build, for example `--executor codex:<model-id>@<effort>`. This provider has no default model and no static model catalog. A CLI catalog listing is not proof of account entitlement or a successful headless build; CLD's normal validation gate applies before production.

An explicit fast request uses `--executor codex:gpt-6-luna@max+fast`.
CLD separates effort and service tier, preserves the full spec in validation
evidence, and refuses warning/fallback output before collecting a candidate.
Fast is opt-in; absent actual-tier telemetry does not prove fast was delivered.
For long max-effort slices, explicitly set `CLD_DISPATCH_TIMEOUT` (default 600
seconds; for example 1200) as described in `references/provider-setup.md`.

The adapter uses a fresh `codex exec --json --ephemeral` session in CLD's isolated Git worktree. It sends the full slice prompt on stdin (`-`), pins `--model`, applies `--sandbox workspace-write` (or an explicit `read-only` setting), and uses `--config model_reasoning_effort="<effort>"` only when an effort is selected. It never uses `resume`, `--last`, a permission-bypass flag, or a positional prompt. The shared process runner bounds timeout and cancellation. JSONL completion permits Git diff capture; CLD's independent acceptance and allowed-files gate decides whether the candidate may be integrated.

Only reported input/output/cache-read token fields enter accounting. Total is derived from input plus output; reasoning and cached input are never added again. The CLI JSONL event does not establish USD cost, so cost remains unknown. A configured cost ceiling therefore follows CLD's existing unknown-usage policy, and model validation requires an explicit validation spend policy. Do not infer entitlement or pricing from a model name.

The recorded Windows canary passed validation, acceptance, and fresh-process integration; other host platforms and process-level interruption are unverified. See `references/provider-setup.md` for the installed CLI check and `docs/plans/codex-support/T16-EVIDENCE.md` in the source repository for its evidence level.


## Codex CLI executor setup

Install and sign in to a current Codex CLI through the official Codex setup instructions. Verify the installed binary with `codex --version` and `codex exec --help`; CLD feature-tests the required noninteractive flags before dispatch. On the target host, choose a model ID and supported effort explicitly, then run a preview with `--dry-run --json` and a budgeted one-slice build. `codex debug models` may show a catalog, but it is not a validation or entitlement guarantee.

Codex uses the current user's documented CLI authentication and configuration. CLD does not read or copy credentials, and the prompt travels on stdin. The default write sandbox is `workspace-write`; this adapter does not enable full-access or approval-bypass flags. Keep CLD's worktree root inside the selected repository and retain the independent acceptance/integration gate.

Usage cost in USD is unknown unless a future CLI event supplies it. Under a cost ceiling, the existing unknown-usage policy blocks by default. Pass an explicit model as `--executor codex:<exact-model-id>@<supported-effort>` and select a validation policy before live execution.

For explicitly requested max effort and fast mode, use
`--executor codex:gpt-6-luna@max+fast`. CLD emits separate configuration
arguments for `model_reasoning_effort="max"` and `service_tier="fast"`.
Only `+fast` is accepted; unknown tiers and tier suffixes on other providers
fail before dispatch. Fast and tier-unspecified specs have separate validation
evidence. Account/model access still requires validation; this syntax is not
proof that fast service was delivered.

With an explicit tier, warning control events or service-tier diagnostics on
stderr fail the dispatch even if Codex exits zero. Reported actual tiers other
than `fast`/`priority` also fail. No candidate diff is collected on that failure;
the worktree and process logs remain available for inspection. Missing actual
tier telemetry remains unverified; CLD cannot detect an unreported server-side
downgrade. Do not silently remove `+fast` and retry.

The shared dispatch deadline defaults to 600 seconds; read-only CLI probes
default to 30 seconds. For a larger max-effort slice, explicitly configure a
finite positive deadline **before** invoking the driver, for example:

```powershell
$env:CLD_DISPATCH_TIMEOUT = "1200"
```

```bash
export CLD_DISPATCH_TIMEOUT=1200
```

This applies to provider dispatches including validation, not read-only probes.
It does not increase attempt or usage budgets. Restore the previous environment
setting after the build; never increase a deadline or retry paid work automatically.

Configuration checked 2026-09-28 against the official
[Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).


For gate meanings and recovery, read `references/delivery-core.md`. CLD judges
the real Git diff and acceptance tests, not the executor's final prose.
