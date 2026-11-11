# v0.7.1 design -- job cancellation for the MCP adapter

Status: revision 4 (2026-11-11), after round-1 reviews (Codex gpt-6.1-sol high,
Gemini 4 Argon high) and round-2 review (Codex; Gemini quota exhausted). Builds on v0.7.0 (`docs/plans/v0.7.0/DESIGN.md`): the
process registry, containment check, fence and job runner are unchanged
foundations.

## Intent

v0.7.0 jobs run to completion; the only way to stop one is to end the runner by
hand. v0.7.1 adds `cld_cancel`: a lead asks a running job to stop, CLD stops it
the way Ctrl+C stops the CLI, escalates to termination after a grace period, and
reports `cancelled` only once nothing it started is still running. It also adds
the MCP adapter to the architecture reference.

## Goals

1. `cld_cancel(job_id)` returns at once; `cld_job` shows `cancelling`, then a
   terminal state.
2. Cooperative first, with Ctrl+C semantics: a cancel is an interrupt, never a
   recorded failure; ledger recovery reconciles the interrupted command next time.
3. Works on Windows: a `--step` blocked in `as_completed` stops promptly.
4. Never report `cancelled` while a CLD process may still run.
5. Architecture reference covers the MCP adapter and cancellation.

## Non-goals

- No change to Ctrl+C behaviour of the plain CLI.
- No partial-result salvage beyond the acceptance boundary below.
- No change to judging, worktrees, integration semantics or the ledger format.

## Anti-goals

- Reporting `cancelled` while a recorded process or group is alive.
- A cancel recorded as a slice, integration, evidence, validation or repair
  failure.
- An executor session calling `cld_cancel` (the executor guard covers it).

## Design

### Engine: one external cancel flag with interrupt semantics (CANCELENGINE)

- `cld.process` gains `EXTERNAL_CANCEL` (a process-level `threading.Event`),
  `start_cancel_watcher()` and `link_external_cancel(event)`. The watcher is
  idempotent; when `CLD_CANCEL_FILE` is set it starts one daemon thread that
  polls for that file every 100 ms and, when it appears, sets `EXTERNAL_CANCEL`
  and every linked event; with the variable unset it starts nothing.
  `run_plan_parallel` links its run-level `cancellation` event, so every wait that
  already observes the scoped event (including the worktree registry-lock wait)
  observes an external cancel too. `cld.cli.main` runs `--integrate` and
  `--mark-repaired` (which do not go through `run_plan_parallel`) inside
  `process_scope(cancel=<event>)` with an event linked the same way, so their
  registry-lock waits also wake on an external cancel.
- **Single choke point.** `run_process` and `dispatch_slot` honour
  `EXTERNAL_CANCEL` like their scoped `cancel`. When the external flag is what
  stopped a `run_process`, it finishes its containment cleanup and then **raises
  `KeyboardInterrupt`** (with `process_result` attached), instead of returning
  `error="cancelled"`. Every caller (executor dispatch, judge and pytest runs,
  model validation and preflight, evidence tasks, integration tests, repair
  verification) therefore sees exactly what Ctrl+C produces today; nothing
  classifies it as a failure. Scoped cancels keep their current behaviour.
- **No failure records on an external interrupt.** Existing `BaseException`
  handlers that persist failure evidence before re-raising
  (`orchestrator.py` session failure, `validate.py` infrastructure-error result,
  `recovery.py` attempt state) must, when `EXTERNAL_CANCEL` is set, re-raise
  without writing a failure (a recovery attempt may be marked `interrupted`, never
  `failed`). Plain Ctrl+C keeps today's behaviour.
- `cld.cli.main` calls `start_cancel_watcher()` for every command an MCP job runs
  (`--new-build`, `--step`, `--integrate`, `--mark-repaired`); `run_plan_parallel`
  also calls it (idempotent) and checks `EXTERNAL_CANCEL` before each dispatch, so
  no new dispatch starts after the flag is set.
- **Acceptance boundary.** The orchestrator checks the flag immediately before a
  slice's collection begins. Before that point a cancel interrupts the slice
  (nothing accepted). Once collection has begun, the slice completes collection
  and its ledger write, then the interrupt takes effect; this matches existing
  durable-collection recovery (`recover_collected`). Evidence mode applies the same
  boundary before its first durable write: `run_ask` checks the flag before
  publishing its ask-ledger entry; once that entry is published, the orchestrator
  completes the build-ledger write before the interrupt takes effect.
- **Git policy.** Git commands run through `git_runner` are not interrupted
  mid-command (they are short and several are recovery-critical); the flag is
  checked between operations. A hung Git hook or filter is handled by the runner's
  escalation after the grace period.

### Jobs: cancel requests, grace, escalation, states (JOBCANCEL)

- `cancel_job(job_id, *, jobs_root=None) -> dict` returns
  `{"job_id", "state", "requested": bool, "reason": str|null}`. Malformed id:
  `ValueError`; unknown id: `LookupError` (as `job_status`).
- **Per-job admission lock.** `cancel_job` and the runner's terminal publication
  both hold `<job-dir>/state.lock` (`cld.locking.file_owner`, resolved path):
  - `cancel_job` under the lock: if `exit.json` exists, or the job is `lost`,
    write nothing, return `requested: false` with the current state; if the
    runner record lacks `"cancel": 1` (a v0.7.0 runner), return
    `requested: false, reason: "legacy_runner"` (stop it manually as documented
    in v0.7.0); if `cancel.request` already exists, leave it (the grace deadline
    is never reset) and return `requested: true, state: "cancelling"`; otherwise
    write `cancel.request` atomically (`{"schema": 1, "requested_at": str}`).
  - The runner publishes `exit.json` under the same lock, so a cancel is either
    admitted before publication (and the runner sees it) or refused after it.
- The runner writes `"cancel": 1` in `runner.json`, sets
  `CLD_CANCEL_FILE=<job-dir>/cancel.request` in the driver environment, watches
  for the file in its 100 ms loop, records the time it first saw it, allows
  `CLD_MCP_CANCEL_GRACE` (default 30 s), then terminates what is left (Windows:
  the Job Object; POSIX: the driver's session group and every recorded group) and
  runs the v0.7.0 containment check with its 5 s confirmation poll.
- Terminal record (`exit.json`, keys unchanged): if a cancel was admitted and the
  driver did not finish normally, `state` is `cancelled` (clean) or
  `cancel_unconfirmed` (unconfirmed), `reason` `cancel_requested` (exited within
  grace) or `cancel_escalated`. If the driver completed normally before noticing
  the cancel -- it printed a Schema-1 response whose `gate_code` equals its exit
  code (any documented gate: 0, 2, 3, 4, 5 or 6) -- the job is `finished` and
  `reason` is `cancel_too_late`.
- State rules, everywhere in `mcp_jobs.py` (exit-record validation, status,
  containment mapping, conflict naming, fence, retention): terminal states are
  `finished`, `died`, `exit_unconfirmed`, `cancelled`, `cancel_unconfirmed`,
  `lost`; active states are `running` and `cancelling` (`cancel.request` present,
  no readable `exit.json`, runner alive). Long polls wait while the state is
  active. An unconfirmed cancel stays `cancel_unconfirmed` (not mapped to
  `exit_unconfirmed`). A `cancelling` job is the active job named in conflicts.
  The fence blocks on `cancel_unconfirmed` like `exit_unconfirmed`. Retention
  treats `cancelled` as confirmed terminal.
- Test faults (only with `CLD_MCP_TESTING=1`; `CLD_MCP_FAULT` may list several,
  comma-separated): `CLD_MCP_FAULT=ignore_cancel`
  omits `CLD_CANCEL_FILE` from the driver environment (forces escalation);
  `kill_fails` (v0.7.0) forces `cancel_unconfirmed`.

### Server: the cld_cancel tool (MCPCANCEL)

- `cld_cancel` (`job_id`): calls `cancel_job`, returns its dict at once; unknown
  id `isError`; malformed id `-32602`; refused by the executor guard; admitted
  like other tool calls (busy rule unchanged). `tools/list` lists nine tools.

### Registration (INSTCANCEL)

- `MCP_TOOLS` in `generator/install_codex.py` gains `cld_cancel`, appended last (Antigravity
  reuses that list for its allow rules). Under `--mcp-approve read-only` it is not
  pre-approved.
- Upgrade path: the existing owned-entry logic already rewrites an intact entry
  owned by the same bundle; the tests pin that a seeded v0.7.0 eight-tool entry
  becomes the nine-tool entry. Edited, foreign and unowned entries stay refused.

### Skills (GENCANCEL)

- One ASCII line in each of the six skill templates and two host workflow
  references: "to stop a job, call `cld_cancel`, then keep polling `cld_job` while
  its state is `running` or `cancelling`; any other state is final, and an
  unconfirmed or lost job blocks the repository until the processes it names are
  gone." Codex SKILL.md limits unchanged.

### Lead work (not a slice)

- Before the build: migrate v0.7.0 tests that pin the eight-tool contract so they
  hold at every integration boundary: `tests/v070/test_mcp_tools.py` checks that
  the eight v0.7.0 tools are listed and nothing unexpected (the exact nine-tool
  list is MCPCANCEL's test); `tests/v070/test_mcp_install.py` `ALL_TOOLS` becomes
  nine (INSTCANCEL integrates in layer 1); write `tests/v071/` (including its `conftest.py`
  with the extended terminal-state set).
- After integration: regenerate bundles and committed plugins
  (`build_skill.py --all` for every host, `build_plugins.py`,
  `check_plugins_fresh.py`), then the full suite.
- Docs: `docs/MCP.md` (cancel, states, upgrade by re-registering), KNOWN-ISSUES,
  CHANGELOG, PRIVACY (the `cancel.request` file).
- Architecture: new `diagrams/10-l3e-mcp-adapter.md` (server, sync tools, job
  runner, registry, containment, fence, cancel flow, per-host registration);
  update `01` (system context: the server and hosts), `02` (packaging:
  `scripts/cld_mcp.py`, `.mcp.json`, `--register-mcp`), `03` (engine subsystems:
  `mcp_server`, `mcp_jobs`, the cancel flag), `06` (process supervision: registry,
  external cancel), `09` (storage: the job directory under `~/.cld/mcp-jobs`,
  outside the repository), and the README index.

## Testing strategy

- Engine: a subprocess runs `run_plan_parallel` with two workers whose fake
  executor waits on a sleeping child via `run_process`, `CLD_CANCEL_FILE` set;
  creating the file ends the run with `KeyboardInterrupt` within 3 s (Windows
  included), children gone. A cancelled pytest run, model validation and
  integration test run each raise `KeyboardInterrupt` and leave no failure in
  the ledger, the validation cache or recovery records. All workers waiting on the
  worktree registry lock wake within 3 s; `--integrate` and `--mark-repaired`
  waiting on that lock (held by another process) end with an interrupt within 3 s. A cancel between evidence execution and
  publication publishes nothing. `dispatch_slot` gives up within 1 s of the flag. A cancel arriving
  after collection began still records the slice as done. No watcher without the
  variable.
- Jobs: cooperative cancel ends `cancelled` / `cancel_requested`;
  `ignore_cancel` with a short grace ends `cancelled` / `cancel_escalated`;
  `kill_fails` ends `cancel_unconfirmed` and fences; a cancel admitted after the
  driver printed a gate-3 or gate-6 response ends `finished` / `cancel_too_late`; `cancelling` in between and
  long polls wait during it; a repeated cancel keeps the first deadline; cancel
  after finish returns `requested: false`; a v0.7.0-style runner record is
  refused with `legacy_runner`; retention deletes old `cancelled` jobs; a
  `cancelling` job is named in conflicts.
- Server: nine tools, guard, error mapping.
- Installers: nine-tool snippet; v0.7.0 entry upgraded on re-register.
- Live check: cancel a real `cld_step` through MCP during an executor dispatch on
  Windows; the next step runs after ledger recovery.

## Builder's choices

Exact texts and internal structure within the rules above.
