# OpenCode as a second executor (option) — 2026-06-09

Reviewed https://opencode.ai/docs/cli/ and https://opencode.ai/docs/zen/.

## Why it's interesting
OpenCode CLI is a clean headless executor, and via the **OpenCode Zen gateway** a *single CLI
fronts 40+ models* (OpenAI GPT-5.x, Anthropic Claude, Google Gemini, plus DeepSeek/Qwen/GLM/
Kimi/Grok and a free tier). That delivers the **per-slice model selection** our pluggable-
executor design wanted — through one adapter instead of one-CLI-per-model.

## CLI mapping (vs our locked Gemini form)
| Need | Gemini CLI (current) | OpenCode CLI |
|---|---|---|
| One-shot headless | `gemini -p "<task>"` | `opencode run "<task>"` |
| Model | `-m gemini-3.1-pro-preview` | `--model provider/model` (e.g. `anthropic/claude-...`) |
| JSON / stats | `-o json` (stats.models.*.tokens) | `--format json` (raw events) + `opencode stats --models` |
| Auto-approve edits | `--yolo --skip-trust` | `--dangerously-skip-permissions` |
| Working dir | cwd | `--dir <path>` |
| Server mode | — | `opencode serve` (HTTP API), `opencode attach` |

An `OpenCodeExecutor(Executor)` adapter would mirror `GeminiExecutor`: build argv, run via the
injected runner, parse token/cost from `--format json` / `opencode stats`, capture diff via git.

## The cost caveat (decision driver)
**OpenCode Zen is metered pay-as-you-go** — "$X per 1M tokens", auto-reload billing
(defaults: top up $20 when balance < $5). Sample rates: Claude Opus 4.8 $5/$25, Sonnet 4.6
$3/$15, Haiku 4.5 $1/$5, **DeepSeek V4 Flash $0.14/$0.28**, plus free-tier models.

Our measured reality: every executor dispatch is **~98% input overhead, non-amortizing**
(45k→158k tokens as a slice grew 8→114 lines). Under **Gemini's flat-rate plan that's $0
marginal** (cost gate = GO). Under **Zen's metered model that overhead becomes real $** — i.e.
routing through Zen would partly *undo the cost win we just locked*, except on the cheapest
tiers where it stays trivial.

## DECISION (2026-06-09)
- **Gemini flat-rate remains the DEFAULT executor.** Preserves $0 marginal.
- **Add `OpenCodeExecutor` as an opt-in second adapter** (registry slot currently held by the
  `composer` stub). Use it for: (a) driving a different flat-rate/free model, or (b) Zen's
  ultra-cheap tier (DeepSeek-class) where 98% overhead is still negligible.
- **Never make a metered provider the default path.** Cost discipline = the whole premise.

## Where this lands in the plan
- Natural home: extend the executor registry (T2.3 already built `get_executor` + a `composer`
  stub) — add `"opencode"` → `OpenCodeExecutor`. Could replace the composer stub outright.
- Not scheduled now (mid-build, Phases 4-6 pending). Revisit at executor-layer hardening or T6
  packaging (multi-model support is a nice "share wider" selling point).
- If pursued: one validation dispatch through `opencode run --format json` to confirm the
  token/cost parse shape, same as the Phase-0 Gemini smoke test.
