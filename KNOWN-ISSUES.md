# Known issues & limitations

Honest scope notes. None of these block normal use; each names its workaround.

## Platform
- **antigravity + cursor dispatch on macOS/Linux is experimental.** Their dispatch handling
  (transcript reading, versioned-binary resolution) was engineered and validated against Windows
  CLI behavior. The **opencode** provider has a clean POSIX path and is the recommended
  non-Windows executor. Field reports welcome.

## Cost reporting
- **Per-dispatch dollar cost is captured for opencode only** (read from its `step_finish.cost`
  events). antigravity is flat-rate (no per-call cost exists); cursor does not report a
  per-dispatch cost, so cursor slices show `$0.00` in `--status` even on metered plans. Token
  counts are captured for all providers.

## cursor upstream
- **cursor-agent long-prompt headless dispatch** has an upstream CLI defect (observed in
  v2026.06.12): long prompts through the shim silently fall back to interactive mode. The
  provider works around it by invoking the versioned `index.js` directly via node
  (`CURSOR_INVOKED_AS=cursor-agent`). If a cursor-agent update changes its install layout, set
  `CURSOR_AGENT_CMD` to override resolution.

## Telemetry
- **`.cld/events.jsonl` is one stream per build**: starting a NEW build (fresh ledger) truncates
  the previous build's stream. If you need to keep a trace, copy it before starting the next
  build. (Designed future fix: per-run subdirectories.)
- **`source` labeling:** a model chosen via the build-level `--executor` flag is labeled
  `default` in dispatch events — only per-slice `executor:` tags get `source=tag`. Escalations
  are labeled `escalated`.

## Validation evidence
- Model validation statuses live in `~/.cld/validation-evidence.json` — **machine-local**. A
  model marked `verified` on one machine shows `untested` on another until validated there
  (the validate-before-trust probe runs automatically on first use).

## Executor catalogs drift
- Provider model catalogs are vendored snapshots; gateways rename/retire model ids (e.g. a
  `kimi-k2.7` → `kimi-k2.7-code` rename was caught live). If a catalogued id fails at dispatch
  with an unknown-model error, check the CLI's own `models` listing and pass the live id
  explicitly via `--executor` or a slice tag.
