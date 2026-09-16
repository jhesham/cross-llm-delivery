# T08 process contract

Updated 2026-09-17. Source engine only; generated plugin refresh remains T12/T17.

`cld.process.run_process(argv, cwd, env=..., stdin=..., timeout=..., cancel=...,
artifact_dir=...)` owns a synchronous command lifecycle. Environment additions
overlay inherited variables. Optional text stdin is UTF-8; otherwise stdin is
closed. No shell is introduced. Binary stdout/stderr go to separate retained files;
UTF-8 replacement decoding is for inspection only and preserves newline bytes.
`ProcessResult` carries the actual return code (or null before completion), error,
elapsed seconds and both paths. Its tuple adapter keeps Git/model-listing callers
compatible without discarding either failure stream.

All three default provider runners use this lifecycle. Dispatch defaults to 600s,
overridable by executor `timeout=` or `CLD_DISPATCH_TIMEOUT`. Model-listing, account
and provider Git probes default to 30s via `CLD_PROBE_TIMEOUT`. Values must be finite
and positive. Authoritative CLI pytest and validation pytest also use containment,
with their existing 600s and 120s deadlines. T09 still owns validation admission and
preflight policy. The general engine Git runner is unchanged in this slice.

Cancellation accepts an Event-compatible token or KeyboardInterrupt. A delivery
worker inherits a shared cancellation token; the coordinator observes futures as
they finish, signals all active workers before joining them, and does not dispatch
queued tasks after cancellation. Recovery checkpoints edits before unwinding. An
explicitly cancelled provider result stops retry/escalation. Interrupted process
metadata is written beside recovery evidence. Timeout remains a failed attempt
subject to the existing bounded retry policy.

On Windows, a Python bootstrap waits for a private pipe payload. The parent assigns
it to a Job Object before releasing argv/stdin. Assignment failure fails closed.
Descendants inherit job membership; breakaway is not enabled. Termination covers
the job, and active-process accounting must reach zero before returning. The job
also has kill-on-close enabled. This uses the current supported Windows job API,
including nested jobs (Windows 8 / Server 2012 onward).

On POSIX, a new session/process group owns the command and its descendants.
Cleanup sends SIGKILL to that group, reaps the leader and waits for remaining live
group members. Linux orphan zombies are already terminated and are left for their
adopter to reap. This is lifecycle containment, not a security sandbox: deliberately
daemonized POSIX children, externally managed services and Windows WMI-created
processes are outside the supported child-creation contract. Abrupt POSIX parent
death is not cooperative cancellation. Cleanup runs after normal exit too, so a
successful CLI cannot leave ordinary background children modifying its candidate.

No candidate inspection, diff capture or worktree cleanup happens until the runner
has stopped the owned process tree. Cleanup errors propagate instead of being
reported as successful completion. Normal timeout cleanup is immediate termination,
not a grace period in which providers may keep editing.

Errors distinguish `missing_binary`, `access_denied`, `launch_error`, `timeout`,
`cancelled`, `nonzero_exit`, and observable `authentication` diagnostics. Completion
guards report `malformed_output`; Cursor also rejects explicit provider error
results. Authentication classification is diagnostic text matching, not an account
or credential verification claim. OpenCode still requires `step_finish`; Cursor
requires a result object; Antigravity requires a MODEL transcript.

`ExecutorResult.process` is optional metadata, preserving legacy construction.
`dispatch.json` retains it; raw feedback is bounded to 4000 characters including
paths. Full stdout/stderr remain separate artifacts, including on failure.
Antigravity retains its additional provider log and a transcript snapshot. Recovery
dispatches place artifacts outside the worktree under the attempt directory;
standalone invocations default to retained OS-temp directories. API callers can set
an artifact parent, which should be outside the candidate. There is no automatic
artifact expiry in this slice. Raw output can contain sensitive provider content;
the lifecycle itself never serializes argv, environment or stdin into diagnostics.

Injected two-argument runners remain supported as explicit test/custom transports.
Their caller owns execution bounds; the engine cannot safely terminate an arbitrary
in-process callable. Production defaults always enforce the process contract.
Provider model, effort, approval flags, OpenCode real-exe resolution and closed stdin,
Cursor bundled-node CA setting, and Antigravity C-drive dispatch behavior remain.

References checked 2026-09-17:

- [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject)
- [Nested Jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs)

Platform execution evidence, including any limits, is in [T08-EVIDENCE.md](T08-EVIDENCE.md).
