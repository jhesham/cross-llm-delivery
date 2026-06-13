# FUTURE: unified LLM-usage view (`/cross-llm-delivery-usage`) — investigation (2026-06-13)

**User request:** "A `/cross-llm-delivery-usage` type modal for both the CLI and VS Code UI
that shows usage of any LLM agents in use during a build — instead of launching multiple CLIs
or logging into web portals to check."

## Feasibility: GOOD. Most data is available LOCALLY (no portal scraping for the two that matter).

### Data sources surveyed (what each provider exposes locally)

| Source | Local access | Quality | Notes |
|---|---|---|---|
| **OpenCode** | `opencode stats` (aggregate $/tokens), `opencode export <sessionID>` (per-session JSON), `~/.local/share/opencode/opencode.db` (SQLite) | **Excellent** | Real cost + tokens, queryable. `opencode export` with NO id BLOCKS (prompts) — always pass a session id. Live total this session: $5.64. |
| **cld engine** | `ExecutorResult.token_usage` per dispatch — ALREADY parsed by both executors and propagated (`orchestrator.py:101`) | **Excellent** | Per-slice, real-time DURING a build, free. The richest build-scoped source. NOT yet persisted (see gap). |
| **Gemini CLI** | No usage flag; quota is the interactive %-screen only. `~/.gemini/history/` exists but no token totals. | **Poor** | But Gemini is FLAT-RATE ($0 marginal) so cost is moot; only "quota % remaining" matters and it isn't cleanly queryable headlessly. Best-effort/omit. |
| **Claude (lead agent)** | `~/.claude/stats-cache.json` exists; `/cost` in-session | **Partial** | Format TBD; the lead agent's own spend. |

### The key gap to close first
The **ledger does NOT persist token/cost** (`ledger.py` tracks slice status only). For a
build-scoped usage view ("this build used X tokens / $Y across N slices on these models"), add
`token_usage` + model + (where available) cost to each slice's ledger entry. The data already
flows through `orchestrator.py:101` — it just isn't written down. This is the highest-value,
lowest-effort piece and unlocks the build-scoped view without touching any provider.

## Two surfaces requested

### 1. CLI `/` command (smaller)
Slash-commands here are skills under `~/.claude/skills/` (e.g. `cross-llm-delivery/`, plus
loose `*.md` like `rac-brief.md`). A `cross-llm-delivery-usage` skill (or a `--usage` subcommand
on `run_delivery.py`) would: read the ledger (build-scoped) + shell `opencode stats` (account
aggregate) + best-effort Gemini quota, and render a combined table. Mostly a read-and-format job.

### 2. VS Code modal (larger)
Two options:
- **Lean:** the `/` command renders a markdown table; the VS Code extension already shows agent
  markdown — so the same skill output appears in both surfaces with near-zero extra work. START HERE.
- **Rich:** a real webview/modal panel (MCP-app/widget style — see the `mcp-server-dev:build-mcp-app`
  skill) with live-updating charts during a build. Much more work; only if the lean version proves
  the need.

## Proposed scope (smallest useful first, to brainstorm)

1. **Persist usage in the ledger** (model + token_usage + cost per slice). Foundational.
2. **`run_delivery.py --usage`** (and/or a `cross-llm-delivery-usage` skill): print a combined
   table — per-build (from ledger) + OpenCode account total (`opencode stats`) + Gemini quota
   (best-effort) + lead-agent `/cost`. Markdown so it renders in BOTH CLI and VS Code.
3. Only if wanted: a rich VS Code webview with live build-time charts.

## Open design questions (for the brainstorm)
- Scope: per-BUILD (this run's ledger) vs. account-AGGREGATE (`opencode stats`) vs. both side-by-side?
- Live (updates as slices complete) vs. on-demand snapshot? Live needs the ledger written per slice.
- Gemini flat-rate quota %: include best-effort, or just label "flat-rate, $0 marginal" and skip?
- Cost truth: OpenCode reports real $; cld's parsed tokens are counts not $ — do we map tokens→$
  via a price table, or only show $ where the provider gives it (OpenCode) and tokens elsewhere?
- Multi-provider future (codex/cursor/etc. if ever added) — keep the source list pluggable.

## Why it fits
The system already routes work across multiple LLMs; a unified usage view is the natural
companion — especially with per-slice executor selection (the OTHER captured feature,
`future-per-slice-executor-by-complexity.md`), where you'll want to SEE what each slice's model
choice cost. Design the two together where they overlap.
