## Codex CLI executor

Choose an exact Codex CLI model ID and optional supported effort for every build, for example `--executor codex:<model-id>@<effort>`. This provider has no default model and no static model catalog. A CLI catalog listing is not proof of account entitlement or a successful headless build; CLD's normal validation gate applies before production.

The adapter uses a fresh `codex exec --json --ephemeral` session in CLD's isolated Git worktree. It sends the full slice prompt on stdin (`-`), pins `--model`, applies `--sandbox workspace-write` (or an explicit `read-only` setting), and uses `--config model_reasoning_effort="<effort>"` only when an effort is selected. It never uses `resume`, `--last`, a permission-bypass flag, or a positional prompt. The shared process runner bounds timeout and cancellation. JSONL completion permits Git diff capture; CLD's independent acceptance and allowed-files gate decides whether the candidate may be integrated.

Only reported input/output/cache-read token fields enter accounting. Total is derived from input plus output; reasoning and cached input are never added again. The CLI JSONL event does not establish USD cost, so cost remains unknown. A configured cost ceiling therefore follows CLD's existing unknown-usage policy, and model validation requires an explicit validation spend policy. Do not infer entitlement or pricing from a model name.

The recorded Windows canary passed validation, acceptance, and fresh-process integration; other host platforms and process-level interruption are unverified. See `references/provider-setup.md` for the installed CLI check and `docs/plans/codex-support/T16-EVIDENCE.md` in the source repository for its evidence level.
