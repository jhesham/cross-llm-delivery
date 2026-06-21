# Complete Windows Headless Provider Dispatch — Design

**Date:** 2026-06-22
**Status:** approved (brainstorming) → writing-plans next
**Scope:** the two post-rebuild-queue items, done as one spec with two independent workstreams.

## Goal

Finish the two remaining provider-adapter items deferred during the spec-#2 rebuild, both rooted in
Windows headless-dispatch quirks:

- **Part A — a new `antigravity` provider.** The Gemini CLI was deprecated and uninstalled; its
  replacement, the Antigravity CLI (`agy`), is installed and authenticated. Add a first-class
  `cld_providers/antigravity/` plugin so builds route to it. Make its Gemini 3.1 Pro (High) the new
  default workhorse; demote the dead `gemini` provider.
- **Part B — fix the `cursor` direct-node dispatch.** cursor-agent's long-prompt core hang is fixed
  upstream, but on Windows the executor still goes through the `.cmd` shim, which mangles long `-p`
  prompts. Switch to invoking the bundled Node entrypoint directly; then promote cursor's trust and
  re-admit it to the shortlist.

The two parts share no code. They live in separate provider folders, get separate task groups,
reviews, and commits, and are sequenced so a snag in one never blocks the other. They share only a
final, gated **live-validation** step (both need the real CLIs to confirm on-disk file writes).

## Non-goals / YAGNI

- No new executor routing tier. The engine has exactly two auto-routing tiers (`quick`, `workhorse`);
  the "heavy" rung is the orchestrator (the lead Claude agent via the gate-4 handoff), never a
  catalog executor. Antigravity's premium models are catalogued for *manual* selection, not a new
  auto-routing tier.
- No removal of the `gemini` provider folder (kept as a demoted/historical adapter, per user).
- No change to the generator/publishing pipeline (spec #2 is complete and untouched here).
- No automated test that calls a real cloud CLI. Live validation is a manual, gated step.

## Background facts (verified 2026-06-22)

- `agy.exe` v1.0.10 at `%LOCALAPPDATA%\agy\bin`, on PATH, authenticated (reuses `~/.gemini/`).
- **Antigravity Windows gotcha:** `agy` writes the model reply to a transcript file at a POSIX path
  `/Users/Administrator/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/transcript.jsonl`.
  On Windows a leading-`/` path resolves to the current drive's root, so it only works when the
  process cwd is on the **C: drive**. stdout is empty by design; the reply lives in the transcript.
  Full recipe + evidence: `docs/notes/antigravity-cli-notes.md`.
- `agy models` (verified live): `Gemini 3.5 Flash (Low|Medium|High)`, `Gemini 3.1 Pro (Low|High)`,
  `Claude Sonnet 4.6 (Thinking)`, `Claude Opus 4.6 (Thinking)`, `GPT-OSS 120B (Medium)`. The label is
  exactly what `--model` expects. `agy models` is TTY-only (empty headless).
- **Cursor:** the core long-prompt hang is fixed on cursor-agent 2026.06.15; the remaining Windows
  issue is the `.cmd` shim mangling long args. Proven fix: invoke `node.exe <version>\index.js`
  directly + env `CURSOR_INVOKED_AS=cursor-agent` + `stdin=DEVNULL`.
  Detail: `docs/notes/cursor-cli-notes.md`.

## The Provider contract (shared interface, unchanged)

Both parts target the existing `Provider` frozen dataclass in `engine/cld/providers_api.py`:
`name`, `make_executor(**kwargs)->Executor`, `catalog: tuple[ModelInfo,...]`, `default_workhorse: str`,
`list_models(runner)->list[str]`, `account_stats`, `account_block`, `account_section`,
`skill_fragment`, `setup_notes`. The executor implements
`run(task: SliceTask, workdir: Path, feedback: str|None) -> ExecutorResult(ok, diff, files_changed,
token_usage, raw_log)`. Diffs are captured via `cld.executors._capture.capture_diff(runner, cwd)`.
`ModelInfo(id, provider, cost_class, capability_class, headless_status, rework_risk, note, tier)`.
Auto-routing facts: `resolve_tier_model(provider, tier, ...)` only considers catalog entries whose
`info.tier == tier`, skips `headless_status=="revalidate"`, prefers `verified`/`likely` over
`untested`, and sorts ties by `(cost_rank, id)`. `default_workhorse()` returns the always-available
fallback + the picker's "default" marker.

---

## Part A — the `antigravity` provider

### A1. Files
`engine/cld_providers/antigravity/{__init__.py, provider.py, SKILL.fragment.md, setup.md}`
(mirrors the four existing providers). Plus a one-line engine tweak in `providers_api.py` (A4) and the
`gemini` demotion (A5). Tests in `tests/`.

### A2. The executor — `AntigravityExecutor`
Same interface as the others. Two behaviours differ from gemini:

1. **cwd ≠ workspace.** The `agy` process runs with **cwd = `C:\Users\Administrator`** (so the POSIX
   transcript path resolves on Windows), while the agent is pointed at the slice worktree via
   `--add-dir <workdir>`. The git diff is captured separately with cwd = workdir.
2. **Capture via transcript, not stdout.** Dispatch argv:
   `agy -p "<prompt>" --model "<label>" --add-dir <workdir> --dangerously-skip-permissions
   --log-file <temp>` with **stdin closed** (the default runner sets `stdin=DEVNULL`).
   `--dangerously-skip-permissions` is antigravity's `--yolo` equivalent — required to edit files
   headlessly. After the process exits:
   - parse the `--log-file` for the `…\brain\<id>\.system_generated\logs\transcript.jsonl` path
     (deterministic; robust under concurrent dispatches), then read that transcript;
   - the reply = the `content` of the JSONL step(s) with `"source":"MODEL"`;
   - `capture_diff(runner, str(workdir))` produces the real deliverable (the worktree diff).
   - `token_usage`: parse from the transcript/log if present, else `{}` (acceptable; not blocking).

`ExecutorResult.ok` is `False` when rc≠0 **or** no transcript / no MODEL step is found — the latter
message must name the cwd-on-C: requirement so a silent path-bug regression surfaces loudly.

The `--model` label is the catalog id's suffix after `antigravity:` (passed verbatim). The default
runner is provider-local: `_default_runner(args, cwd) -> (rc, out)`, subprocess with the given cwd,
`stdin=subprocess.DEVNULL`, `capture_output=True, text=True, encoding="utf-8", errors="replace"`.
The executor accepts the worktree cwd from the orchestrator but **overrides the dispatch cwd to the
user home on the C: drive** via a helper `_dispatch_cwd() -> str`: take `Path.home()` (normally
`C:\Users\<user>`); if its drive is not `SystemDrive` (typically `C:`), rebuild it onto `SystemDrive`
(`<SystemDrive>\Users\<name>`). This is the cwd passed to the `agy` dispatch (NOT to `capture_diff`,
which always uses the worktree). The git diff is still captured with the worktree cwd.

### A3. Catalog — 8 models; display bucket vs. auto-routing tier split
Ids are `antigravity:<exact label>`. `capability_class` is the **display bucket** (`quick`/`workhorse`/
`heavy`); `tier` is what the **auto-router** climbs (`quick`→`workhorse`). `tier` is assigned narrowly
(one model per routing tier = that tier's default) so auto-routing is deterministic; all 8 remain
manually selectable via browse / `--executor`. All `cost_class="flat"` (flat-rate/quota, $0 marginal).

| id (`antigravity:…`)             | capability_class | tier        | headless_status |
|----------------------------------|------------------|-------------|-----------------|
| Gemini 3.5 Flash (Low)           | quick            | None        | likely          |
| Gemini 3.5 Flash (Medium)        | quick            | quick       | likely          |
| Gemini 3.5 Flash (High)          | quick            | None        | likely          |
| Gemini 3.1 Pro (Low)             | workhorse        | None        | likely          |
| Gemini 3.1 Pro (High)  ← default | workhorse        | workhorse   | likely          |
| GPT-OSS 120B (Medium)            | workhorse        | None        | untested        |
| Claude Sonnet 4.6 (Thinking)     | workhorse        | None        | likely          |
| Claude Opus 4.6 (Thinking)       | heavy            | None        | likely          |

`rework_risk="low"` for the Gemini/Claude families; `"medium"` for GPT-OSS (untested). Notes describe
each briefly (e.g. Opus: "premium reasoning; flat-rate via Antigravity; pin manually for hard slices").
Auto-routing result: easy→`Gemini 3.5 Flash (Medium)`, standard/complex→`Gemini 3.1 Pro (High)` (=
the default workhorse). `list_models(runner)` returns the static 8 ids (since `agy models` cannot be
read headlessly) so all are present in `available_ids` for browse/manual pin.

### A4. Default-workhorse engine change
In `providers_api.default_workhorse()`, replace the hardcoded single `"gemini"` preference with an
ordered preference tuple `_WORKHORSE_PREFERENCE = ("antigravity", "gemini")`: when multiple providers
are registered, return the `default_workhorse` of the first preference present; otherwise the first
registered. Result with all providers present: `antigravity:Gemini 3.1 Pro (High)`. (Single-provider
trimmed bundles are unaffected — rule 1 still returns that provider's own default.)

### A5. Demote the `gemini` provider
In `cld_providers/gemini/provider.py`, set the model's `headless_status="revalidate"` (auto-routing
skips `revalidate`) and update its `note` to "CLI deprecated 2026-06-21; superseded by antigravity".
It stays registered and browsable but is out of the default/auto-routing path. The generator's
per-provider bundle for gemini is unaffected.

### A6. Skill fragment + setup
`SKILL.fragment.md`: the antigravity slice of skill docs — the 8 models, flat-rate economics, and the
Windows cwd-on-C: caveat (mirrors how cursor's fragment carries its caveat). `setup.md`: install
`agy`, interactive login (reuses `~/.gemini/`), the cwd-on-C: note. Both are vendored automatically
into a generated `cross-llm-antigravity` skill by the existing generator.

---

## Part B — cursor direct-node dispatch fix

### B1. Files
`engine/cld_providers/cursor/provider.py` only (+ its tests). No engine-core change.

### B2. The change
- Replace `_cursor_cmd() -> str` (returns the `.cmd` path) with `_cursor_invocation() -> list[str]`
  returning a **direct-node argv prefix**: on Windows, locate the lexically-latest
  `%LOCALAPPDATA%\cursor-agent\versions\<v>\`, then return `[<node_exe>, <…\index.js>]` — preferring
  a bundled `node.exe` in the version dir, else system `node`. `CURSOR_AGENT_CMD` override still
  honored (returns `[override]`). Non-Windows: `["cursor-agent"]`.
- `_default_runner`: add `stdin=subprocess.DEVNULL` and set env `CURSOR_INVOKED_AS=cursor-agent`
  (merged onto `os.environ`). Keep utf-8/replace + stderr-on-failure capture.
- `run()` dispatch becomes `[*_cursor_invocation(), "-p", prompt, "--output-format", "json",
  "--workspace", cwd, "--model", model_id, "--force", "--trust"]`. No other logic changes;
  `parse_cursor_usage` + `capture_diff` are unchanged.
- `account_stats()` (which also calls `_cursor_cmd()`): update to the new invocation for the `about`
  call too, so the account section keeps working.

### B3. Trust follow-through
After live-validation (B-validation), promote `cursor:composer-2.5` `headless_status`
`untested`→`verified`, and re-admit cursor to the `recommend()` shortlist (it was excluded only
because of this dispatch bug — confirm whether the exclusion lives in `recommend()` and lift it).

### B4. Testing
Unit tests via an injected runner asserting: the dispatch argv starts with the direct-node prefix
(contains an `index.js`, not a `.cmd`), `CURSOR_INVOKED_AS` is set, stdin handling is correct, and the
existing parse/capture path still works. Retarget the existing cursor tests that assumed the `.cmd`
invocation. (`_cursor_invocation`'s filesystem probe is tested with a temp fake versions dir.)

---

## Shared: live validation (gated, manual — not CI)

After both parts pass unit review, one manual validation pass with the real CLIs (the controller runs
these, since they need auth + write to disk):

- **Antigravity:** a real one-slice build via `AntigravityExecutor` with `--add-dir <tmp worktree>`
  and a file-writing prompt → confirm the file appears on disk in the worktree and `capture_diff`
  returns it. On success promote the exercised model(s) `likely`→`verified`.
- **Cursor:** a real long multi-line slice via `CursorExecutor` (direct-node) → confirm it writes the
  file (the long-prompt path that previously broke). On success do B3 (promote + re-admit).

If a live step fails, capture the evidence and treat it as a normal bug in that part's workstream
(the other part is unaffected).

## Testing strategy summary

- **CI / no network:** unit tests for both executors via injected runners + on-disk fakes (fake
  transcript.jsonl for antigravity; fake versions dir for cursor); provider-registration tests
  (antigravity: 8 ids, default_workhorse correct; gemini demoted to revalidate); updated
  cross-provider regression (`catalog()` count 9→17; `default_workhorse()` == antigravity Pro High).
- **Manual / gated:** the two live-validation slices above.
- Full existing suite stays green.

## Risks & mitigations

- *Antigravity transcript format changes* → the parser keys on `source=="MODEL"` content and is
  isolated in one function; covered by a fake-transcript unit test.
- *cwd-on-C: assumption brittle on non-default installs* → derive the home dir from `Path.home()`
  forced onto `SystemDrive`, with a clear `ok=False` message if the transcript is absent.
- *Cursor bundled-node path differs across versions* → probe for `node.exe` then fall back to system
  `node`; `CURSOR_AGENT_CMD` override remains the escape hatch.
- *Live validation reveals `--add-dir` doesn't write files headlessly* → contained to Part A; the
  spec's CI portion still lands, and we iterate on the executor (documented open question).

## Done criteria

- `antigravity` provider registered with 8 catalogued models; `default_workhorse()` returns
  `antigravity:Gemini 3.1 Pro (High)`; `gemini` demoted to `revalidate`; catalog count 17.
- `cursor` executor dispatches via direct-node (no `.cmd`), `CURSOR_INVOKED_AS`+`stdin=DEVNULL` set.
- All unit tests + the full existing suite green.
- Live validation done (or any failure captured as a contained follow-up); trust promotions applied.
- STATUS.md updated: post-rebuild queue cleared (or the residual live item noted).
