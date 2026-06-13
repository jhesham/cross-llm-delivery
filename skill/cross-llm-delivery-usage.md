---
name: cross-llm-delivery-usage
description: Show LLM usage for a cross-llm-delivery build — this build's per-slice model/tokens/cost (from the ledger) plus the OpenCode account total. One view instead of multiple CLIs / web portals.
---

# Cross-LLM Delivery — Usage View

Render a combined usage table for a build. Run:

    python skill/scripts/run_delivery.py <plan.md> --ledger <ledger-path> --usage

The positional plan path is required by argparse but is NOT read for `--usage` (pass the build's
plan or any placeholder). `--ledger` points at the build's ledger (default `.cld-ledger.json`).

It prints a **markdown table** — renders identically in the CLI and the VS Code extension chat:

- **Per-slice rows:** each slice's model + total tokens + cost (cost blank where the provider
  doesn't report one — e.g. flat-rate Gemini).
- **Build total tokens.**
- **## OpenCode account:** the account aggregate from `opencode stats` (total cost + input/output).

On-demand snapshot — re-run to refresh. If `opencode stats` is unavailable the table degrades to
ledger-only with an "OpenCode stats unavailable" note (never errors). Gemini is flat-rate
($0 marginal), so its slices show tokens with no per-token cost.

Example output:

    | Slice | Model | Tokens | Cost |
    |---|---|---|---|
    | T1 | opencode/deepseek-v4-pro | 37167 | 0.014 |
    | T2 | gemini:gemini-3.1-pro-preview | 50 |  |

    **Build total tokens:** 37217

    ## OpenCode account
    Total cost: $5.85
    Input: 1.6M
    Output: 90.7K
