# v0.7.0 design -- optional MCP adapter and the same lead experience on every host

Status: revision 7.2 (2026-11-08): step-1.0 host checks recorded. Scope cut after three review rounds: no cancellation in v0.7.0 (planned for v0.7.1); round-4 contract fixes. Evidence:
three throwaway spikes (kept with the maintainer's notes). Spike results are
version-specific: Claude Code 2.1.318, Codex CLI 0.167.0, Antigravity agy 1.5.2.

## Intent

Leads drive CLD by running `run_delivery.py` in a shell. That causes friction:
headless Antigravity refuses shell commands without exact-command allow rules,
Codex `exec` has similar approval limits, quoting and paths break (spaces, Git
Bash path rewriting, `Set-Location …; python …`), PowerShell hides the real exit
code, and each host's skill carries its own shell guidance.

v0.7.0 adds an **optional MCP server** exposing CLD's commands as typed tools and
registers it on all three lead hosts. The CLI stays the source of truth: each
tool runs the bundle's own scripts and returns their JSON unchanged.

## Goals

1. A stdio MCP server with **no third-party dependencies** (standard library plus
   CLD's own modules), shipped in every bundle as `scripts/cld_mcp.py`.
2. Typed tools for every lead action; long-running actions run as durable jobs.
3. Per-tool approval on every host: read-only tools can be pre-approved, spending
   and state-changing tools stay an explicit choice.
4. One canonical registration per host, backed by the all-executors bundle.
5. Skills on all three hosts prefer the tools when present; CLI instructions stay
   as the fallback.

## Non-goals

- No change to judging, worktrees, ledger, integration or executor dispatch
  beyond the Antigravity isolation fix below.
- No direct model calls through the server; executors are reached only through a
  plan.
- No HTTP/SSE transport. No MCP inside executor processes. No Antigravity plugin
  packaging. No credentials handled by the server.
- No MCP declaration inside Codex plugins (spike 3 on Codex 0.167: `${PLUGIN_ROOT}`
  was not substituted in `.mcp.json` and relative paths failed); Codex
  registration is installer-written.

## Anti-goals

- Any default that dispatches or spends without an explicit executor, validation
  policy and attempt budget.
- Changing the CLI's JSON contract to suit MCP.
- Reporting a job cancelled, finished or released while any CLD process it
  started may still be running.
- Editing a host configuration the user did not ask to change, or an entry CLD
  does not own.

## Architecture

```
lead host ──MCP stdio──► scripts/cld_mcp.py ──► cld.mcp_server
                                                  │ sync tools: bounded subprocess
                                                  │ job tools: cld.mcp_jobs
                                                  ▼
                       job runner (python -I scripts/cld_mcp.py --run-job <job-dir>)
                         holds the repo reservation lock, launches the driver,
                         waits, writes the exit record atomically
                                                  ▼
                       scripts/run_delivery.py (unchanged CLI)
```

| Component | Location | Responsibility |
|---|---|---|
| Entry script | `skill/scripts/cld_mcp.py` (vendored as `scripts/cld_mcp.py`) | Same `sys.path` shim as `run_delivery.py`; `--run-job <dir>` calls `cld.mcp_jobs.run_job`; `--resolve-job <id> --confirm` calls `cld.mcp_jobs.resolve_job` (human-only); otherwise `cld.mcp_server.main(scripts_dir=<own dir>)`. |
| Server | `engine/cld/mcp_server.py` | JSON-RPC loop, negotiation, schemas, validation, sync tools, job tools via `mcp_jobs`. |
| Jobs | `engine/cld/mcp_jobs.py` | Job runner, reservations, durable records, containment check, fence, retention. |
| Engine support | `engine/cld/cli.py`, `engine/cld/cli_response.py`, `engine/cld/process.py` | `--new-build --json` reports the ledger backup path; the process registry (see Jobs). |
| Antigravity isolation | `engine/cld_providers/antigravity/provider.py` | Executor dispatches deny the `cld` MCP tools. |
| Generator | `generator/build_skill.py`, `generator/build_plugins.py`, skill templates | Vendor the entry script; Claude plugin `.mcp.json`; MCP section in skills. |
| Installers | `generator/install_codex.py`, `generator/install_antigravity.py` | Separate `--register-mcp` / `--unregister-mcp` actions with full transaction guarantees. |

## Executables and the driver contract

- The server resolves its scripts directory from its own file location
  (`Path(__file__)` of the entry script, passed into `main(scripts_dir=…)`), never
  from the working directory. Delivery commands run `<scripts>/run_delivery.py`;
  model listing runs `<scripts>/list_models.py`. Both with `sys.executable`.
- `CLD_DRIVER` and `CLD_MODELS` override those paths **for tests only**.
- `cld_list_models` is the one exception to the Schema-1 contract: it returns the
  picker's advisory JSON unchanged and adds no `--host`. Every other tool adds
  `--host <CLD_HOST>` (default `mcp`).
- Synchronous tools run with a timeout (`CLD_MCP_SYNC_TIMEOUT`, default 45 s);
  a timeout kills that subprocess tree and returns `isError` with the reason, and
  the server keeps serving.

## Protocol

- Newline-delimited JSON-RPC 2.0 on stdio. Only JSON-RPC lines go to stdout;
  diagnostics go to stderr.
- **Version negotiation:** supported versions `2025-06-18`, `2025-03-26`,
  `2024-11-05`. If the client requests one of them, reply with it; otherwise
  reply with `2025-06-18` (the latest supported), per the MCP lifecycle spec.
- `serverInfo: {"name": "cld", "version": <v>}` where `<v>` is parsed from the
  `v<X.Y.Z>` in the GENERATED banner of `<scripts_dir>/../SKILL.md` (bundles carry
  no VERSION file), else `<repo>/VERSION` when run from source, else `0.0.0`; capabilities
  `{"tools": {}}`. Requests without `id` are notifications (no reply). `ping`
  returns `{}`.
- Errors, without terminating the server: malformed JSON → `-32700` (id `null`);
  not an object / missing `method` → `-32600`; unknown method → `-32601`;
  invalid `tools/call` params (unknown tool, wrong argument types, missing
  required arguments) → `-32602`. Domain failures (driver error, refused path,
  job conflict, unknown job) are tool results with `isError: true`.
- Tool results carry the JSON as `content[0].text` and as `structuredContent`.

## Tools

All paths must be absolute (refused otherwise, before anything runs). Executor,
validation policy and attempt budget are required wherever a dispatch can
happen; there are no defaults.

| Tool | Kind | Command | Arguments |
|---|---|---|---|
| `cld_preview` | sync | `run_delivery.py <plan> --repo <repo> --dry-run --json` | `plan`, `repo` |
| `cld_status` | sync | `run_delivery.py --status --repo <repo> --json` | `repo` |
| `cld_list_models` | sync | `list_models.py --json` (advisory JSON, no `--host`) | none |
| `cld_new_build` | sync, mutating | `run_delivery.py <plan> --repo <repo> --new-build --json` | `plan`, `repo` |
| `cld_step` | job | `run_delivery.py <plan> --repo <repo> --step --workers <w> --executor <e> --validation-policy <p> --budget-attempts <n> --json` | `plan`, `repo`, `executor`, `validation_policy` (`deny`/`unmetered`/`allow`), `budget_attempts` (≥1), `workers` (1–4, default 1) |
| `cld_integrate` | job | `run_delivery.py <plan> --repo <repo> --integrate --integration-tests <selector> --json` | `plan`, `repo`, `integration_tests` |
| `cld_mark_repaired` | job | `run_delivery.py <plan> --repo <repo> --mark-repaired <slice> --json` | `plan`, `repo`, `slice_id` |
| `cld_job` | poll | — | `job_id`, `wait_seconds` (0–45, default 30) |

**Executor guard:** if the server's environment has `CLD_EXECUTOR_DEPTH` set, it
refuses every mutating tool (`cld_new_build`, `cld_step`, `cld_integrate`,
`cld_mark_repaired`) with `isError`. Read-only tools still work.

## Jobs

**Scope of v0.7.0.** Jobs run to completion (or to CLD's own attempt budget).
There is no cancel tool in v0.7.0; cooperative cancellation (`cld_cancel`, a cancel
channel in the driver) is planned for v0.7.1. Everything below that keeps a
repository safe when a driver crashes or a runner dies is in v0.7.0.

**Public API of `cld.mcp_jobs`** (the tests import exactly these):
`start_job(kind, repo, argv, *, entry_script, jobs_root=None) -> dict`,
`job_status(job_id, *, jobs_root=None, wait_seconds=0) -> dict`,
`check_fence(repo, *, jobs_root=None) -> list[dict]` (unresolved jobs blocking the repo),
`resolve_job(job_id, *, jobs_root=None, confirm=False) -> dict`,
`purge(jobs_root=None, max_age_days=7) -> int`, `run_job(job_dir) -> int`;
exceptions `JobConflict` and `JobFenced` (both subclass `RuntimeError`).
`jobs_root=None` means `CLD_MCP_JOBS` if set, else `~/.cld/mcp-jobs`.

**Pinned return and record keys:**
- `start_job` returns `{"job_id": str, "state": "running", "kind": str, "repo": str}`.
- `exit.json`: `{"schema": 1, "state": "finished"|"died"|"exit_unconfirmed",
  "returncode": int|null, "ended_at": str, "result": object|null, "reason":
  str|null, "containment": "clean"|"unconfirmed"}`.
- `job_status` returns `{"job_id": str, "state": str, "returncode": int|null,
  "result": object|null, "reason": str|null, "containment": str|null,
  "identities_incomplete": bool}` (values from `exit.json` when it exists).
- `check_fence` items: `{"job_id": str, "state": str, "alive": [identity...],
  "live_groups": [int...], "identities_incomplete": bool}`.

**Job runner.** `start_job` spawns `[sys.executable, "-I", entry_script,
"--run-job", <job-dir>]`; the entry script's own `sys.path` shim bootstraps the
bundle's `cld`, and `-I` keeps an ambient `PYTHONPATH` or another installed copy
out. Spawn flags: Windows `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP |
CREATE_BREAKAWAY_FROM_JOB` (retry without breakaway on `OSError`, recording
`breakaway: false`); POSIX `start_new_session=True`.

The runner (`run_job`) owns the job:
1. Acquires the repository reservation (below) and writes `runner.json`
   atomically: `{"schema": 1, "runner": <identity>, "reservation": <key>,
   "driver": null}`.
2. Starts the driver **gated**, so nothing runs before it is contained and
   recorded:
   - Windows: the runner creates its own Job Object (kill-on-close, no breakaway),
     starts the driver through the same stdin-gated bootstrap `cld.process` uses,
     assigns it to the Job Object, records it, then sends the payload.
   - POSIX: the driver starts in its own new session through a small gated
     launcher that waits on an inherited pipe (`pass_fds`, leaving stdin free) and
     then replaces itself with the target (`os.execvp`), so the recorded pid is
     the driver's own; the runner records it, then releases the gate.
   - Recording means rewriting `runner.json` atomically with `"driver":
     <identity>` before the gate opens. If recording fails, the runner kills the
     still-gated driver and the job ends `died` with reason `record_failed`.
   - Driver environment: `CLD_PROCESS_REGISTRY=<job-dir>/processes.jsonl`.
3. Waits in ticks of at most 100 ms for driver exit.
4. **Containment check on exit:** the job is containment-clean only when the
   driver has exited, no process is left in the containment (Windows: the Job
   Object's active-process count from `QueryInformationJobObject` is 0; POSIX: the
   driver's session group is empty, `os.killpg(pgid, 0)` raises
   `ProcessLookupError`), and every `processes.jsonl` spawn without a matching reap
   is gone. Reaped is not the same as clean: a reaped child's own group is still
   checked.
5. If not clean, the runner terminates what is left (Windows: terminate the Job
   Object; POSIX: kill the driver's session group and each recorded group still
   alive), then polls the containment check every 10 ms for up to 5 s before
   deciding (termination completes asynchronously).
6. Writes `exit.json` atomically (temp, fsync, rename) with the exit code, end
   time, parsed result, and `containment: "clean" | "unconfirmed"`. Then releases
   the reservation and exits.

**Engine support (ENGINEMCP slice).** **Process registry:** when
`CLD_PROCESS_REGISTRY` is set, `run_process` records each child before it does any
work: on Windows after `job.assign(...)` and before the bootstrap payload is sent;
on POSIX by starting the child through the same pipe-gated, exec-in-place launcher
and writing the record before releasing it. If the record cannot be written, the child is killed
before it runs and `run_process` returns an error. On exit it appends a reap line.

**Pinned record formats** (shared by MCPJOBS, ENGINEMCP and the test stubs):
- Identity: `{"pid": <int>, "pgid": <int|null>, "start_time": <token>}`.
  `start_time` is: Windows, the `GetProcessTimes` creation `FILETIME` as an integer
  `(high << 32) | low`; Linux, field 22 of `/proc/<pid>/stat` (parsed after the
  closing `)` of the command) as an integer; other POSIX, the stripped output of
  `ps -o lstart= -p <pid>` as a string. `pgid` is null on Windows.
- `processes.jsonl`: one JSON object per line, `{"event": "spawn", ...identity}`
  or `{"event": "reap", "pid": <int>, "start_time": <token>}`; each line flushed
  and fsynced.
- **What an identity refers to.** The recorded process is the one CLD itself
  launched and contained. On Windows that is the stdin-gated bootstrap (the actual
  command runs as its child, inside the same Job Object, which is what contains
  it); on POSIX it is the actual command, because the launcher execs in place.
- A line that does not parse is **torn**. A job with torn lines, or a missing or
  unreadable `runner.json`, has `identities_incomplete: true`.

**Durable state.** Job directory `<CLD_MCP_JOBS>/<job-id>/` (default
`~/.cld/mcp-jobs`): `request.json`, `runner.json`, `stdout.txt`, `stderr.txt`,
`processes.jsonl`, `exit.json`, optional `resolution.json`. Job ids are 32
lowercase hex characters, refused otherwise before a path is built. All lock and
job paths are built from **resolved** directories, because
`cld.locking.file_owner` refuses a path whose `resolve()` differs from its
`absolute()` (for example Windows short names such as `ADMINI~1`).

**State rules** (`job_status`, also from a restarted server):
- With a readable `exit.json`: `finished` (driver JSON parsed), `died`, or
  `exit_unconfirmed` when `containment == "unconfirmed"`.
- Without one and the runner identity alive: `running`.
- Without one (or with an unreadable one) and the runner gone: `lost`.
- Long-poll waits up to `wait_seconds` (at most 45).

**Process identity.** A pid is trusted only together with its `start_time`; a
mismatch means the pid now belongs to another process, which is treated as gone and
never signalled. Once a job has a terminal record, nothing signals its pids again.

**Repository reservation and fence.**
- An OS file lock on `<jobs>/locks/<sha256(resolved repo)>.lock`, held by the
  runner for the whole job and released by the OS if the runner dies.
- Starting a job: a short-lived spawn lock for the same key, then the fence, then
  a free reservation, then spawn, then up to 10 s for `runner.json`; a runner that
  cannot take the reservation exits with `exit.json` reason `conflict`.
- **Fence.** A free OS lock never on its own authorises a job. Before any mutating
  job, `check_fence` examines the repo's jobs in `lost` or `exit_unconfirmed`. For
  each, every recorded identity (runner, driver, spawns without a reap) is checked,
  **and every recorded POSIX process group** (the driver's session group and the
  `pgid` of every spawn, reaped or not, including groups whose leader is gone) is
  probed with `os.killpg(pgid, 0)`; a group with any live member counts as alive.
  A recorded group id cannot be attributed with certainty once its leader is gone,
  so a live group always fences (resolve manually if it is unrelated).
  If all are gone and the records are complete, it writes `resolution.json`
  (`{"reason": "processes_gone", ...}`) and the job no longer blocks. If any is
  alive, or `identities_incomplete` is true, the job blocks and `JobFenced` names
  it with the surviving pids.
- **Windows note.** Because the runner's Job Object is kill-on-close, a runner
  that dies takes its contained processes with it; `lost` jobs on Windows normally
  resolve at the next fence check.

**Stopping a job in v0.7.0** (documented for users; no tool does this):
end the runner process named in `runner.json`. On Windows its Job Object stops the
driver and every executor with it. On POSIX the driver keeps running in its own
session, and the fence keeps the repository blocked until the user also stops the
driver and executor processes the fence error names. CLD's ledger recovery
reconciles the interrupted step on the next command.

**Resolving a blocked repository** (documented for users):
1. Normal: stop the processes the error names (they are CLD's own driver or
   executor processes), then retry the operation; the fence re-checks and resolves.
2. Records incomplete, or a live group the user has checked is unrelated: run
   `python <bundle>/scripts/cld_mcp.py --resolve-job <job-id> --confirm` (a
   human-only command, not an MCP tool). It never overrides a live CLD process: if any recorded identity (runner, driver
   or spawn) is alive with a matching pid **and** start-time token, it refuses,
   names it, and writes nothing, even with `--confirm`. Only when every recorded
   identity is gone does `--confirm` override what remains uncertain (torn or
   missing records, or a live recorded group the user has checked is unrelated),
   writing `resolution.json` with `"reason": "manual"`; the evidence stays in
   place.

**Test-only fault injection,** honoured only when `CLD_MCP_TESTING=1`:
`CLD_MCP_FAULT=kill_fails` makes the runner's termination calls no-ops **and**
creates the Windows Job Object without kill-on-close, so a surviving process really
survives the runner's exit; `CLD_MCP_FAULT=record_fails` makes recording the driver
fail.

**Deadlines.** Synchronous tools time out after `CLD_MCP_SYNC_TIMEOUT` (default
45 s, under Codex's 60 s default MCP tool timeout). `cld_new_build` runs through
the job runner (so its process has durable ownership) and the tool waits for it
up to the same deadline, returning the job id for polling if it is still running.
`job_status` waits at most 45 s.

**Implementation notes (the spike code is not reused).** Windows calls set
explicit `argtypes`/`restype` (`wintypes.HANDLE`, `DWORD`, `BOOL`) as
`_windows_job.py` does. POSIX: a process that spawned a child reaps it
(`os.waitpid(pid, os.WNOHANG)`, tolerating `ChildProcessError`); a zombie is not
alive.

**Retention.** On server start, delete job directories older than 7 days only if
they have a confirmed terminal state (`finished`, `died`, or `resolution.json`) and
a free reservation. Everything else is kept.

**Planned for v0.7.1:** `cld_cancel` returning at once, a `CLD_CANCEL_FILE` watcher
in the driver that sets a process-level cancel flag checked by `run_process` and the
Antigravity slot wait (so a step blocked in `as_completed()` wakes on Windows too),
escalation after a grace period, and the `cancelling` / `cancelled` /
`cancel_unconfirmed` states. The v0.7.0 registry, containment check and fence are
the foundation it builds on.

## Executor isolation (Antigravity)

The Antigravity executor uses the user's global agy configuration with
`--dangerously-skip-permissions`, so a globally registered `cld` server would be
visible to executor sessions. Two layers:

1. **Provider:** executor dispatches pass the session-only setting
   `--settings '{"permissions":{"deny":["mcp(cld/*)"]}}'`, keeping the rest of the
   executor's behaviour unchanged. Confirmed in step 1.0 on agy 1.5.2: agy accepts it
   together with `--dangerously-skip-permissions`, the deny wins, and the wildcard
   form is honoured ("Permission denied for mcp(cld/cld_status)").
   Antigravity has no evidence dispatch (`supports_evidence=False`, and
   `evidence_mode/ask.py` refuses it before dispatch); that stays unchanged and is
   pinned by a regression test.
2. **Server:** the executor guard above refuses mutating tools when
   `CLD_EXECUTOR_DEPTH` is set (agy is expected to pass its environment to stdio
   servers; the live check confirms).

The Claude executor already isolates MCP (`--strict-mcp-config` with an empty
server list); the Codex executor already disables configured MCP servers. Tests
pin both.

## Registration (same lead experience on every host)

**One canonical server per host, from the all-executors bundle.** Only
`cross-llm-delivery` (Claude Code, Codex) and `cross-llm-delivery-agy`
(Antigravity) register MCP. Single-provider skills still use the `cld_*` tools
when present and pass their own executor explicitly; the unified server serves
any executor. Registering from a single-provider bundle is refused.

| Host | How | Approval |
|---|---|---|
| Claude Code plugin | Generated `.mcp.json` in the `cross-llm-delivery` plugin only: `command` `python`, `args` `["${CLAUDE_PLUGIN_ROOT}/skills/cross-llm-delivery/scripts/cld_mcp.py"]`, `env.CLD_HOST` `claude-code`. | Claude prompts per tool; headless leads use `--allowedTools mcp__plugin_cross-llm-delivery_cld__<tool>`. |
| Claude Code standalone | Documented `claude mcp add cld -- <python> <abs>/scripts/cld_mcp.py`. | `mcp__cld__<tool>`. |
| Codex | `install_codex.py --register-mcp --scope-root <dir> --bundle <installed cross-llm-delivery>` writes `[mcp_servers.cld]` into `<dir>/.codex/config.toml`: absolute `command` (`sys.executable`), absolute script path, `env.CLD_HOST="codex"`, `enabled_tools` (all eight), per-tool `tools.<tool>.approval_mode`. Pinned to Codex CLI 0.167.0 behaviour. The exact TOML is pinned below (confirmed on Codex CLI 0.167.0 in step 1.0). | `--mcp-approve read-only` (default): read-only tools approved, mutating tools left to the host's normal approval (denied in `codex exec`). `--mcp-approve all`: every tool approved. |
| Antigravity | `install_antigravity.py --register-mcp --scope user --scope-root <home> --bundle <installed cross-llm-delivery-agy>` merges `mcpServers.cld` into `<home>/.gemini/config/mcp_config.json` (absolute command and script, `env.CLD_HOST="antigravity"`). Workspace scope refused (agy reads MCP config globally). | Not written. The result lists the recommended `permissions.allow` rules (`mcp(cld/<tool>)`). |

**Codex snippet (pinned, step 1.0 on Codex CLI 0.167.0).** A tool with
`approval_mode = "approve"` runs without a prompt; a tool without it is refused in
`codex exec` ("requires approval, but approval policy is never").

`--mcp-approve read-only` (default):

```toml
[mcp_servers.cld]
command = "<absolute sys.executable>"
args = ["<absolute installed bundle>/scripts/cld_mcp.py"]
env = { CLD_HOST = "codex" }
enabled_tools = ["cld_preview", "cld_status", "cld_list_models", "cld_new_build", "cld_step", "cld_integrate", "cld_mark_repaired", "cld_job"]

[mcp_servers.cld.tools.cld_preview]
approval_mode = "approve"

[mcp_servers.cld.tools.cld_status]
approval_mode = "approve"

[mcp_servers.cld.tools.cld_list_models]
approval_mode = "approve"

[mcp_servers.cld.tools.cld_job]
approval_mode = "approve"
```

`--mcp-approve all`: the same `[mcp_servers.cld]` table plus
`default_tools_approval_mode = "approve"` (no per-tool tables), confirmed in
spike 1.

**Ownership.** The owned entry records the installation it belongs to: the
absolute path of the installed bundle and a content hash of the entry. For TOML,
a comment block `# cld-mcp owner=<bundle path> sha256=<hash>` …
`# end cld-mcp`; for JSON, an `"_cld_owner": {"bundle": <path>, "sha256": <hash>}`
key inside the entry.
- Register refuses an existing `cld` entry that is unowned, owned by a different
  bundle path, or whose content no longer matches its recorded hash (edited).
- Unregister removes the entry only when `--bundle` matches the recorded owner
  and the hash matches; otherwise it refuses and changes nothing.
- Skill `--uninstall` refuses while an owned registration still points at that
  bundle, and tells the user to `--unregister-mcp` first (no dangling server).
- **Same scope only.** A registration may only reference the owned installation in
  the same scope root as the configuration it is written to: Codex
  `<scope-root>/.agents/skills/cross-llm-delivery` with
  `<scope-root>/.codex/config.toml`; Antigravity
  `<home>/.gemini/config/skills/cross-llm-delivery-agy` with
  `<home>/.gemini/config/mcp_config.json`. Uninstall therefore only has to check
  its own scope's configuration.
- **One transaction boundary.** Register, unregister and skill uninstall all hold
  the same scope-level OS lock (`<skills dir>/.cld-mcp.lock`, built from resolved
  paths) across their checks and their write or delete, so a registration can never
  be published for a bundle that uninstall is removing.

**Transactions (same guarantees as skill installs).** Registration is a separate
action from installing the skill, so the two never need joint rollback (the
skill must already be installed and owned; register checks that first).
- `--preview` with `--register-mcp`/`--unregister-mcp` writes nothing and reports
  the planned change.
- Collision and ownership checks happen before any write.
- Writes: under the scope lock above, re-read the file, write a temp file in the same directory, validate it (`tomllib` / `json`),
  fsync, atomic replace. On any failure, the original file is untouched.
- A configuration path that is a symlink or junction, or whose parent directories
  are, is refused (reuse the installers' `_is_link` checks).
- Output stays a single JSON object per invocation.
- Command line: `--preview` may be combined with `--register-mcp` or
  `--unregister-mcp` (they are not added to the existing mutually exclusive
  `--preview/--install/--uninstall` group).
- The installers import `cld.locking` by adding the repository's `engine/`
  directory to `sys.path` (they run from `generator/`), and wait up to 10 s for
  the scope lock (`file_owner(..., wait_seconds=10)`), reporting `OwnerBusy` as a
  refusal.
- Order: link checks, preview handling and target-existence checks run before the
  scope lock file is created, so `--preview` and refused operations create
  nothing (existing tests assert this).

**Skills.** Each template gains a short "MCP tools" section: if `cld_*` tools are
available, use them (preview, then `cld_new_build` when starting, then `cld_step`,
then poll `cld_job` with `wait_seconds` 45 until a terminal state, act on
`gate_code`, then `cld_integrate` and poll). The CLI instructions remain as the
fallback. The added text is ASCII only (generated skills must encode as cp1252),
links only to files inside the bundle, and keeps the rendered Codex `SKILL.md`
within the existing limits of 130 lines and 9000 characters.

## Engine change

On v0.6.1, `--new-build --json` already emits Schema-1 JSON (`command`,
`gate_code`, `run_id`). The change: include the ledger backup path in
`artifacts` (`artifacts.ledger_backup`) when a previous ledger was backed up.

## Privacy and security

PRIVACY.md and SECURITY.md describe the new persistent job files (location,
contents: arguments, paths, driver output; retention 7 days) and the
configuration entries the register actions write.

## Testing strategy

- Stub driver and stub picker scripts selected via `CLD_DRIVER` / `CLD_MODELS`.
- Job tests use stub drivers that sleep, exit without JSON, write JSON then keep
  running, and **spawn a child in its own process group/session** to prove the
  containment check and the fence.
- Concurrency tests start jobs from **separate OS processes** at the same time.
- A generated-bundle test runs `scripts/cld_mcp.py` with `CLD_DRIVER` unset from
  an unrelated working directory.
- Installer tests cover preview, write failure (simulated), an edited owned
  entry, concurrent edits, a symlinked/junctioned config path, and unregister by
  a non-owning bundle.
- Live checks after the build exercise every host through **integration**, not
  just acceptance.

## Builder's choices

Exact error texts and internal module structure, within the rules above. Record formats and the public API are pinned, not choices.
