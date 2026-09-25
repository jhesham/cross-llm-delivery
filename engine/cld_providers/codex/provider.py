"""T16 Codex executor adapter: wires the T15 offline contract into cld.process.

The adapter owns only the process boundary: ambient recursion guard, read-only
capability probes, one bounded stdin dispatch through the injected runner, JSONL
parsing, and (on valid completion alone) Git diff capture through the shared
``cld.executors._capture``. Allowed-files enforcement stays with CLD's
independent candidate verifier; JSONL item/file events and final prose are
never treated as acceptance. Provider registration, generated bundles, and CLI
default-model policy are owned by the lead and are intentionally NOT here.
"""
from __future__ import annotations

import os
from pathlib import Path

from cld.executors._capture import CaptureError, capture_diff
from cld.executors.base import ExecutorResult, SliceTask
from cld.process import deadline_seconds, feedback as process_feedback, run_process

from .contract import (
    CodexContractError,
    build_invocation,
    check_capabilities,
    parse_exec_output,
)

# Structural JSONL failures mean the event stream itself cannot be trusted, so
# they collapse to one actionable error. Semantic failures (turn_failed,
# authentication, timeout, ...) already name the actionable cause.
_STRUCTURAL_ERRORS = ("malformed_output", "event_order", "invalid_usage")


def _ambient_depth() -> int:
    """Ambient CLD_EXECUTOR_DEPTH; anything but absent/zero blocks dispatch."""
    value = os.environ.get("CLD_EXECUTOR_DEPTH")
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return -1


class CodexExecutor:
    """Executor backed by the Codex CLI (``codex exec --json --ephemeral``).

    ``runner(argv, cwd, **kwargs)`` is the shared bounded-process contract
    (returns an object with returncode/stdout/stderr/error/metadata(), like
    ``cld.process.ProcessResult``); ``git_runner`` is the two-tuple runner used
    only for post-completion diff capture. The probe is read-only and never
    invokes inference; ambient user auth/config is respected as-is and prompts
    travel over stdin, never argv or process metadata.
    """

    def __init__(self, *, model, effort=None, sandbox="workspace-write",
                 runner=run_process, git_runner=run_process,
                 timeout=None, cancel=None, artifact_dir=None):
        if not isinstance(model, str) or not model.strip():
            raise ValueError("CodexExecutor requires an explicit, nonempty model id")
        self._model = model
        self._effort = effort
        self._sandbox = sandbox
        self._runner = runner
        self._git_runner = git_runner
        self._timeout = timeout
        self._cancel = cancel
        self._artifact_dir = artifact_dir

    def _build_prompt(self, task: SliceTask, feedback: str | None = None) -> str:
        """Bounded one-slice brief: task, exact allowlist, acceptance test."""
        allowed = ", ".join(task.files)
        prompt = (
            f"Implement the following so that the acceptance tests pass.\n\n"
            f"{task.brief}\n\n"
            f"You may only create/modify these files: {allowed}\n"
            f"Acceptance tests: {task.acceptance_test_path}\n"
            f"Do not edit the test file. Run pytest yourself and iterate until green."
        )
        if feedback:
            prompt += (
                f"\n\nYour previous attempt did not pass. {feedback}\n"
                f"Address this specifically before trying again."
            )
        return prompt

    def _probe(self, argv: list[str], cwd: str):
        """Read-only capability probe with a finite deadline; never inference."""
        return self._runner(argv, cwd, timeout=deadline_seconds())

    def run(self, task: SliceTask, workdir: Path, feedback: str | None = None) -> ExecutorResult:
        # The recursion guard precedes ANY process, including the probes.
        if _ambient_depth() != 0:
            return ExecutorResult(
                ok=False, diff="",
                raw_log=("Recursive dispatch blocked: CLD_EXECUTOR_DEPTH is already set "
                         "in the ambient environment, so this executor is itself running "
                         "inside a dispatched executor; refusing to dispatch another one."),
                process={"error": "recursive_dispatch"},
            )
        cwd = str(Path(workdir).resolve())

        # Fail on local misconfiguration before spawning any process.
        prompt = self._build_prompt(task, feedback)
        try:
            invocation = build_invocation(self._model, cwd, prompt,
                                          effort=self._effort, sandbox=self._sandbox)
        except CodexContractError as exc:
            return ExecutorResult(ok=False, diff="",
                                  raw_log=f"Refusing to build a Codex dispatch: {exc}",
                                  process={"error": "invalid_invocation"})

        # Capability gate: feature-test the installed CLI, never infer support.
        version = self._probe(["codex", "--version"], cwd)
        help_out = self._probe(["codex", "exec", "--help"], cwd)
        for label, probe in (("codex --version", version), ("codex exec --help", help_out)):
            if probe.error:
                return ExecutorResult(
                    ok=False, diff="",
                    raw_log=(f"Codex CLI probe '{label}' failed ({probe.error}); install or "
                             f"repair the Codex CLI and ensure it is on PATH."),
                    process={**probe.metadata(), "error": probe.error},
                )
        try:
            check_capabilities(version.stdout, help_out.stdout)
        except CodexContractError as exc:
            return ExecutorResult(ok=False, diff="",
                                  raw_log=f"Codex CLI capability check failed: {exc}",
                                  process={**help_out.metadata(), "error": "missing_capability"})

        # Fresh isolated session: prompt on stdin ('-'), no resume/--last, no shell.
        proc = self._runner(
            invocation.argv, invocation.cwd,
            stdin=invocation.stdin, env=invocation.env,
            timeout=deadline_seconds(self._timeout, dispatch=True),
            cancel=self._cancel, artifact_dir=self._artifact_dir,
        )
        metadata = dict(proc.metadata())
        output = (proc.stdout or "") + (proc.stderr or "")
        raw_log = process_feedback(output, metadata)

        outcome = parse_exec_output(proc.stdout, proc.stderr, proc.returncode,
                                    process_error=proc.error)
        if not outcome.ok:
            error = outcome.error or "malformed_output"
            if error in _STRUCTURAL_ERRORS or error.startswith("event_cardinality"):
                error = "malformed_output"
            # No valid completion: never capture a candidate diff.
            return ExecutorResult(ok=False, diff="", files_changed=[],
                                  raw_log=raw_log,
                                  process={**metadata, "error": error})

        # Valid completion alone permits diff capture; the worktree diff (not
        # JSONL file events) is the candidate, verified independently by CLD.
        try:
            diff, files_changed = capture_diff(self._git_runner, invocation.cwd)
        except CaptureError as exc:
            return ExecutorResult(ok=False, diff="", files_changed=[],
                                  raw_log=raw_log + f"\nGit diff capture failed: {exc}",
                                  process={**metadata, "error": "diff_capture"})

        # Forward only evidenced fields; the shared accounting layer derives
        # total and marks total_source=derived_input_output. Never invent cost
        # or cache-write; missing usage stays unknown.
        token_usage = {key: value for key, value in outcome.usage.items()
                       if key in ("input", "output", "cache_read")}
        return ExecutorResult(ok=True, diff=diff, files_changed=files_changed,
                              token_usage=token_usage, usage_raw=outcome.usage_raw,
                              raw_log=raw_log, process=metadata)
