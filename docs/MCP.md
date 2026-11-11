# MCP tools (v0.7.0; cancellation v0.7.1)

CLD ships an optional MCP server, `scripts/cld_mcp.py`, in every bundle. It exposes
CLD's lead commands as typed tools, so a lead (Claude Code, Codex or Antigravity)
calls tools instead of running `run_delivery.py` in a shell. The CLI stays the
source of truth: every tool runs the bundle's own scripts and returns their JSON
unchanged. The server needs only Python's standard library and the bundle's
vendored `cld`.

If the tools are not available, the skills fall back to the CLI instructions.

## Tools

| Tool | Kind | Runs |
|---|---|---|
| `cld_preview` | read-only | `run_delivery.py <plan> --repo <repo> --dry-run --json` |
| `cld_status` | read-only | `run_delivery.py --status --repo <repo> --json` |
| `cld_list_models` | read-only | `list_models.py --json` (advisory picker JSON) |
| `cld_new_build` | mutating | `--new-build --json`, through the job runner; waits up to 45 s |
| `cld_step` | job | `--step --workers <1-4> --executor <spec> --validation-policy <deny/unmetered/allow> --budget-attempts <n> --json` |
| `cld_integrate` | job | `--integrate --integration-tests <selector> --json` |
| `cld_mark_repaired` | job | `--mark-repaired <slice> --json` |
| `cld_job` | read-only | Poll a job: `job_id`, `wait_seconds` 0-45 (default 30) |
| `cld_cancel` | mutating | Ask a running job to stop: `job_id`; returns at once |

All paths must be absolute. `cld_step` has no defaults for the executor,
validation policy or attempt budget. Job tools return a `job_id` at once; poll
`cld_job` with `wait_seconds` 45 while the state is `running` or `cancelling`;
any other state (`finished`, `died`, `cancelled`, `exit_unconfirmed`,
`cancel_unconfirmed`, `lost`) is final. Act on the result's `gate_code`.

Executors never get these tools. The Claude Code executor runs with
`--strict-mcp-config` and no servers, the Codex executor disables every
configured MCP server, and Antigravity executor sessions pass
`--settings '{"permissions":{"deny":["mcp(cld/*)"]}}'`. The server also refuses
every mutating tool when `CLD_EXECUTOR_DEPTH` is set.

## Register the server

Register only the all-executors bundle (`cross-llm-delivery`, or
`cross-llm-delivery-agy` on Antigravity); it serves every executor.
Single-provider skills use the same tools and pass their own executor.

**Claude Code plugin.** The `cross-llm-delivery` plugin declares the server in
its `.mcp.json` (`python` on `PATH`). Claude Code prompts per tool; headless
leads allow tools with
`--allowedTools=mcp__plugin_cross-llm-delivery_cld__cld_status,...`.

**Claude Code standalone skill.**

```bash
claude mcp add --scope user cld -e CLD_HOST=claude-code -- <python> <home>/.claude/skills/cross-llm-delivery/scripts/cld_mcp.py
```

Do not register both: remove the standalone entry
(`claude mcp remove --scope user cld`) if you install the plugin.

**Codex.** Install the skill first, then register it in the same scope root:

```bash
python generator/install_codex.py --install --scope-root <home> --bundle dist/codex/cross-llm-delivery
python generator/install_codex.py --register-mcp --scope-root <home> --bundle <home>/.agents/skills/cross-llm-delivery
```

This writes an owned `[mcp_servers.cld]` table into `<home>/.codex/config.toml`
with absolute paths. `--mcp-approve read-only` (the default) pre-approves
`cld_preview`, `cld_status`, `cld_list_models` and `cld_job`; the mutating tools
(including `cld_cancel`) follow Codex's normal approval (refused in `codex exec`). `--mcp-approve all`
approves every tool. Codex plugins do not declare the server.

**Antigravity.** Antigravity reads MCP configuration globally, so registration is
user scope only:

```bash
python generator/install_antigravity.py --install --scope user --scope-root <home> --bundle dist/antigravity/cross-llm-delivery-agy
python generator/install_antigravity.py --register-mcp --scope user --scope-root <home> --bundle <home>/.gemini/config/skills/cross-llm-delivery-agy
```

This merges `mcpServers.cld` into `<home>/.gemini/config/mcp_config.json`. No
permissions are written; the output lists the `permissions.allow` rules
(`mcp(cld/<tool>)`) you can add. A headless `agy -p` lead honours them.

**Registration rules (Codex and Antigravity).** `--preview` with
`--register-mcp` or `--unregister-mcp` writes nothing. The entry records its
owner (bundle path and a content hash); an unowned, foreign or hand-edited entry
is refused and the file is left byte-identical. Unregister with the same
`--bundle`. Skill `--uninstall` is refused while an owned registration points at
the bundle, so run `--unregister-mcp` first. Linked (symlinked or junctioned)
configuration paths are refused. Each invocation prints one JSON object.

## Jobs

Jobs run in a detached runner (`python -I scripts/cld_mcp.py --run-job <dir>`)
that holds a per-repository reservation, records every process CLD starts, and
writes `exit.json` only after checking that nothing it started is still running.
One job per repository runs at a time; a second gets a conflict naming the
running job.

Job files live in `~/.cld/mcp-jobs/<job-id>/` (or `CLD_MCP_JOBS`):
`request.json`, `runner.json`, `stdout.txt`, `stderr.txt`, `processes.jsonl`,
`exit.json`, `cancel.request` and `state.lock` when a job is cancelled, and,
after a fence resolution, `resolution.json`. Finished jobs older
than 7 days are deleted when a server starts; unresolved ones are kept.

**Stopping a job (v0.7.1).** Call `cld_cancel` with the job id, then keep polling
`cld_job`. The job shows `cancelling`; CLD interrupts the step the way Ctrl+C does
(in-flight executor and test processes are stopped and nothing is recorded as a
failure), waits up to `CLD_MCP_CANCEL_GRACE` seconds (default 30), then terminates
whatever is left. It ends `cancelled` once everything it started is gone, or
`cancel_unconfirmed` (which fences the repository) if it cannot confirm that. A
slice already being collected when the cancel arrives is still accepted. If the
command finished before the cancel took effect, the job ends `finished` with
reason `cancel_too_late`. CLD's ledger recovery reconciles the interrupted
command on the next run.

Jobs started by a v0.7.0 server cannot be cancelled (`legacy_runner`). Stop them
by ending the runner process named by `runner.json` (`runner.pid`); on POSIX also
stop the driver and executor processes.

**Upgrading a registration.** Re-run `--register-mcp` after updating the skill so
Codex lists `cld_cancel` (`enabled_tools` is explicit); an intact entry owned by
the same bundle is rewritten in place.

**A blocked repository.** If a runner died (`lost`) or could not confirm that
everything stopped (`exit_unconfirmed`), the next mutating job for that
repository is refused while any recorded process or POSIX process group is still
alive, and the error names them. Stop those processes and retry; the check then
records `resolution.json` and continues. If the records are incomplete, or a live
group is unrelated, a person can resolve it:

```bash
python <bundle>/scripts/cld_mcp.py --resolve-job <job-id> --confirm
```

It never overrides a live recorded CLD process.

## Environment

| Variable | Meaning |
|---|---|
| `CLD_HOST` | Host name passed as `--host` (set by each registration). |
| `CLD_MCP_JOBS` | Job directory root (default `~/.cld/mcp-jobs`). |
| `CLD_MCP_SYNC_TIMEOUT` | Deadline for synchronous tools in seconds (default 45). |
| `CLD_MCP_CANCEL_GRACE` | Seconds a cancelled job may take to stop before termination (default 30). |
