---
name: cross-llm-delivery-usage
description: Show a CLD build's recorded per-slice model, tokens and cost, with available provider account summaries or a bounded JSON snapshot.
---

# Cross-LLM Delivery — Usage View

From the installed skill directory, read the build's ledger with an absolute
repository path:

```bash
python scripts/run_delivery.py --repo <absolute-repo> --usage
python scripts/run_delivery.py --repo <absolute-repo> --usage --json
```

No positional plan is needed and neither command dispatches an executor.
The default ledger is `<repo>/.cld-ledger.json`; use `--ledger <absolute-path>`
for another ledger. Relative explicit ledger paths use the invocation directory.

The human-readable Markdown table shows per-slice models, known token/cost
totals and unknown values. Available account sections come from providers used
by the ledger: OpenCode uses `opencode stats`, and Cursor has its own account
summary. These external CLI queries are account snapshots, not this build's
metered totals. Missing account data does not authorize inference or a retry.

`--usage --json` reads persisted build evidence without provider account queries.
Use `--slice <id>` or `--attempt <id>` for bounded JSON detail. See the installed
`references/observability.md` for the snapshot fields.

Only provider-reported usage/cost is known. A subscription, free catalog label
or missing cost field does not establish zero dollars. Antigravity usage may
be entirely unknown; Cursor/Codex dollar cost remains unknown when not reported.
Claude CLI cost estimates are retained as estimates, not billed CLD cost.
