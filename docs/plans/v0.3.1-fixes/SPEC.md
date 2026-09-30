# v0.3.1 review fixes — design

Status: design approved in conversation 2026-09-30; awaiting written-spec review.
Scope: seven defects found in the post-0.3.0 in-depth review. No new provider;
the Claude executor is a separate v0.4.0 sub-project with its own spec.

## Goal and success criteria

v0.3.1 makes CLD stop giving wrong answers and stop paying for failures that
cannot succeed, without weakening any acceptance guarantee.

- Validation evidence survives across lead sessions and hosts unless something
  that affects the provider actually changed.
- Tool caches, packaging metadata and test-run artifacts no longer reject a
  correct slice, block a baseline, or block integration.
- An executor error that cannot succeed on retry costs at most one dispatch and
  never escalates to another model.
- An npm-installed Codex CLI on Windows is usable, or fails with an actionable
  gate-5 message, never a false "missing binary".
- A Codex lead without network access is told so before or at its first
  dispatch, and does not burn retries on it.
- CLD-managed worktrees can be cleaned up safely and explicitly.
- Every existing guarantee holds: protected inputs stay protected, model output
  never decides acceptance, unknown usage is never zero, nothing is merged into
  the user's checkout, no automatic spend.

## Fix 1 — validation context fingerprint

**Defect.** `cld/admission.py` `validation_context` hashes `sorted(os.environ.items())`.
Per-session variables (`CLAUDE_CODE_SESSION_ID`, `CLAUDE_PID`, VS Code IPC
handles) change every session, so `fresh_record` never matches and every new
session re-validates (paid) or blocks under the default `deny` policy.

**Design.**
- `Provider` gains `context_env: tuple[str, ...]` — exact variable names or
  `PREFIX_*` patterns that affect that provider's CLI identity, account, routing
  or configuration.
- A shared base set applies to every provider: `HTTP_PROXY`, `HTTPS_PROXY`,
  `ALL_PROXY`, `NO_PROXY` (and lowercase forms), `SSL_CERT_FILE`,
  `SSL_CERT_DIR`, `REQUESTS_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`.
- Provider sets: codex `CODEX_HOME`, `CODEX_CLI_CMD`, `OPENAI_*`; opencode
  `OPENCODE_*`; cursor `CURSOR_*`; antigravity `AGY_CMD`.
- The fingerprint hashes only the selected names and values. The stored record
  keeps the sorted selected **names** (never values) for diagnostics.
- `validation_context` contract becomes `2`. Contract-1 evidence is treated as
  stale: one explicit revalidation under the user's spend policy, never silent
  acceptance and never silent spend.

**Tests.** Unrelated variable change keeps evidence fresh; a change to a
selected variable (e.g. `CODEX_HOME`, `HTTPS_PROXY`) invalidates it; values
never appear in stored records; contract-1 records are stale.

## Fix 2 — candidate capture and judge snapshot

**Defect.** `capture_tree` force-adds ignored files, but `_is_noise` exempts only
`__pycache__`, `.pytest_cache` and `*.pyc/*.pyo`. `snapshot` fingerprints every
file in the judge checkout, including files a test run creates. Reproduced
rejections: `.ruff_cache`, `.mypy_cache`, `*.egg-info` at capture;
`.hypothesis/` and `.coverage` at judge time (which also fails the baseline
preflight and integration, so such projects cannot use CLD at all).

**Design.**
- Extend noise to: `.mypy_cache`, `.ruff_cache`, `.hypothesis`, `.tox`, `.nox`,
  `htmlcov`, `.eggs`, any `*.egg-info` directory, `.coverage` and
  `.coverage.*` files, and any directory containing a `CACHEDIR.TAG` file.
- Noise is exempt only when the path is **new and untracked** relative to the
  dispatch base. Tracked files with those names are judged normally. Protected
  defaults (`conftest.py`, `pyproject.toml`, `tests/`, …) are unaffected.
- `snapshot` fingerprints only paths tracked in the candidate tree. New
  untracked files created by the acceptance run cannot alter the candidate and
  are recorded (names only) in attempt evidence, not treated as mutation.
  Modification or deletion of a tracked file, and any symlink/junction, still
  fail.
- An executor placing real source in an ignored, non-noise path is still
  force-added and judged against the allowlist (unchanged).

**Tests.** The five review probes become regressions (capture: ruff, mypy,
egg-info; judge, baseline and integration: `.hypothesis`, `.coverage`).
Negative tests: tracked-file mutation during the judge run fails; an edited
protected input fails; a tracked file named like noise is still judged.

## Fix 3 — final executor errors

**Defect.** `deliver_slice` turns every failed `ExecutorResult` into judge
feedback and retries (default 3 dispatches); the rung planner then escalates to
another model. Reproduced: a permanent authentication error dispatched 3 times.
Codex `+fast` warnings are detected after a complete paid turn and retried with
the identical configuration.

**Design.**
- One shared set, `FINAL_EXECUTOR_ERRORS`, in the engine: `authentication`,
  `missing_binary`, `access_denied`, `launch_error`, `missing_capability`,
  `invalid_invocation`, `recursive_dispatch`, `service_tier_warning`,
  `service_tier_mismatch`, `timeout`, `network_unavailable`, `diff_capture`.
- On a final error, `deliver_slice` stops its retry loop and returns a result
  marked `final_error`. The orchestrator does not try further rungs. The slice
  is recorded as blocked (gate 5) with worktree and evidence retained and an
  actionable message per error (re-authenticate, install/override the CLI,
  set `CLD_DISPATCH_TIMEOUT`, run with network access, remove `+fast`
  explicitly, …).
- Still retried: `nonzero_exit`, `turn_failed`, `error_event`,
  `malformed_output`, and ordinary acceptance failures.
- Accounting records the attempt with its error and any reported usage.
- Timeouts are final by decision (matches KNOWN-ISSUES: do not automatically
  retry or raise limits).

**Tests.** One dispatch, no escalation, gate 5 for each final error (auth,
timeout, `service_tier_warning` minimum); acceptance failure still retries;
accounting shows one finished attempt with the error.

## Fix 4 — Windows Codex launcher

**Defect.** The Codex adapter, probes and picker run bare `codex`. Without a
shell, Windows resolves only `codex.exe`; an npm-only install (`codex.cmd`)
fails as `missing_binary` with "install or repair the Codex CLI".

**Design.**
- `resolve_codex_command()` used by probes, dispatch, the picker catalog and
  the validation context:
  1. `CODEX_CLI_CMD` (must be an existing absolute file);
  2. `codex.exe` found on `PATH` (non-Windows: `codex`);
  3. on Windows, the native binary behind an npm shim, following the package's
     own layout: the platform package's `vendor/<target-triple>/bin/codex.exe`,
     then the legacy `@openai/codex/vendor/<target-triple>/bin/codex.exe`.
- If only `codex.cmd` exists, block with gate 5 naming the shim and
  `CODEX_CLI_CMD`. Never dispatch through `cmd.exe`: `--config key="value"`
  arguments are exactly what shims mangle (the same lesson as Cursor/OpenCode).

**Tests.** Fixture layouts for each resolution step and for shim-only; a
model-free `--version` check against this machine's npm install.

## Fix 5 — Codex lead without network

**Defect.** A Codex lead runs the driver inside its own sandbox, whose default
`workspace-write` mode has no network. Executor dispatches (including nested
`codex exec`) need network. The Codex host bundle does not say so. Live
failure not reproduced; the recorded live Codex-lead runs likely relied on
approved escalations.

**Design.**
- Documentation: the Codex host `SKILL.template.md`, `codex-workflow.md` and
  `delivery-core.md` state that `--step`, validation and repair-verification
  dispatches make network calls, and that inside a Codex sandbox those commands
  must be run with network-enabled/escalated permissions.
- Runtime, best effort: if `CODEX_SANDBOX_NETWORK_DISABLED=1` is present in the
  driver environment, block with gate 5 before any dispatch. (The standalone
  `codex sandbox` runner does not set it; the check is cheap and harmless.)
- Runtime: a failed dispatch whose output matches connection-failure
  signatures (DNS resolution failure, `ENOTFOUND`, `ECONNREFUSED`, network
  unreachable, Windows socket `os error 10013`, "stream disconnected before
  completion") is classified `network_unavailable`, a final error (fix 3).
  Only failed dispatches are inspected, so a false positive stops instead of
  retrying.

**Tests.** Env-var block precedes any dispatch; each signature maps to
`network_unavailable`; a successful dispatch mentioning those words is
unaffected.

## Fix 6 — worktree cleanup

**Defect.** Integration worktrees are always retained; only collected slice
worktrees are removed. Observed: 18 leftover worktrees, 29 registrations,
178 MB under `.cld/`. No cleanup command exists.

**Design.**
- `run_delivery.py --gc --repo <dir> [--json]` previews and changes nothing.
  `--apply` performs removal. JSON lists each candidate with reason and action.
- Eligible: worktrees of slices `integrated` in the current build; integration
  worktrees whose transaction is `passed` but is not the recorded integration,
  or `failed` once a passed integration is recorded (transaction records carry
  no timestamps, so "superseded" means a recorded pass exists); stale
  registrations (`git worktree prune`). The recorded integration's own worktree
  and transactions in any other state are kept.
- Earlier builds' worktrees are listed and removed only with
  `--include-previous`, and only when they have no uncommitted changes.
- Never removed: worktrees of failed, blocked, needs-repair or in-progress
  slices; anything outside the recorded root; `.cld/runs/` evidence;
  `refs/cld/*` recovery refs. Takes the build writer lock; verifies each
  worktree's identity (`verify_worktree`) before removal.

**Tests.** Preview is read-only; apply removes only eligible entries; retained
categories survive; a dirty previous-build worktree is kept; out-of-root paths
are refused.

## Fix 7 — leftovers

- `deliver_slice` drops its stale `gemini-3.1-pro-preview` default; `model`
  defaults to `None` (no fabricated model name). Seventeen existing tests call
  it without a model, so it is not made mandatory.
- Telemetry/ledger `source`: explicit `--executor` → `"chosen"`, slice tag →
  `"tag"`, true build default → `"default"`, escalation → `"escalated"`.
  Closes issue #12 (credit the original contributor).
- The Codex catalog no longer forces labels through cp1252; encoding safety
  applies where text is printed.

## Delivery plan outline (detailed in PLAN.md)

1. **Sitting 1 — lead.** Commit this spec and the plan; commit red acceptance
   tests for fixes 1–7; lead implements fixes 1 and 2 (verification semantics).
2. **Sitting 2 — CLD dogfood.** Installed CLD skill with executor
   `codex:gpt-6-luna@max+fast` builds slices for fixes 3+5 runtime, 4, 2's
   noise entries, 6 and 7; lead reviews and integrates. The installed engine
   still has defect 1, so expect one Luna validation probe under
   `--validation-policy allow`; announced before dispatch.
3. **Sitting 3 — lead.** Docs (fix 5 guidance, KNOWN-ISSUES, CHANGELOG,
   README where affected), regenerate bundles/plugins, full offline suite, CI
   (Windows/Ubuntu × Python 3.11/3.14), install updated skills, update issues
   #12 and #14.

## Release gate (v0.3.1)

All four CI jobs green on the exact source; bundle/plugin freshness passes;
installed skills coherent with that source. Tagging, public push and GitHub
release happen only after the user's explicit go-ahead.

## Out of scope

The Claude executor provider (v0.4.0 spec); POSIX/macOS live validation;
Cursor cost capture (#10); behavioural grading in the acceptance gate.
