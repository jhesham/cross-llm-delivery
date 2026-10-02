"""Claude Code executor: one isolated, subscription-billed `claude -p` session per slice.

The adapter owns only the process boundary: recursion guard, model-free
capability probes, one bounded stdin dispatch, JSON result parsing and, on valid
completion alone, the shared Git diff capture. CLD's independent verifier
decides acceptance. There is no default model; callers pin an exact ID and effort.
"""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from cld.executors._capture import CaptureError, capture_diff
from cld.executors.base import ExecutorResult, SliceTask
from cld.native_cli import resolved_runner
from cld.process import deadline_seconds, feedback as process_feedback, run_process
from cld.providers_api import Provider, register_provider

from .catalog import list_models
from .contract import ClaudeContractError, build_invocation, check_capabilities, parse_result
from .launcher import ClaudeLauncherError, resolve_claude_command
from .preflight import account_context, run_auth_preflight

# Structural output failures mean the result itself cannot be trusted.
_STRUCTURAL = ("malformed_output", "invalid_usage")


def _ambient_depth() -> int:
    """Ambient CLD_EXECUTOR_DEPTH; anything but absent/zero blocks dispatch."""
    value = os.environ.get("CLD_EXECUTOR_DEPTH")
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return -1


def _fail(error, log, metadata=None):
    return ExecutorResult(ok=False, diff="", files_changed=[], raw_log=log,
                          process={**(metadata or {}), "error": error})


class ClaudeExecutor:
    """Executor backed by the Claude Code CLI on the user's subscription."""

    def __init__(self, *, model, effort=None, runner=run_process, git_runner=run_process,
                 timeout=None, cancel=None, artifact_dir=None):
        if not isinstance(model, str) or not model.strip():
            raise ValueError("ClaudeExecutor requires an explicit, nonempty model id")
        self._model, self._effort = model, effort
        self._runner, self._git_runner = runner, git_runner
        self._timeout, self._cancel, self._artifact_dir = timeout, cancel, artifact_dir

    def _prompt(self, task: SliceTask, feedback):
        prompt = (f"Implement the following so that the acceptance tests pass.\n\n{task.brief}\n\n"
                  f"You may only create/modify these files: {', '.join(task.files)}\n"
                  f"Acceptance tests: {task.acceptance_test_path}\n"
                  "Do not edit the test file. Run pytest yourself and iterate until green.")
        if feedback:
            prompt += f"\n\nYour previous attempt did not pass. {feedback}\nAddress this specifically."
        return prompt

    def run(self, task: SliceTask, workdir: Path, feedback: str | None = None) -> ExecutorResult:
        # The recursion guard precedes ANY process, including the probes.
        if _ambient_depth() != 0:
            return _fail("recursive_dispatch", "Recursive dispatch blocked: CLD_EXECUTOR_DEPTH is "
                         "already set; refusing to start another executor.")
        cwd = str(Path(workdir).resolve())
        try:
            invocation = build_invocation(self._model, cwd, self._prompt(task, feedback), effort=self._effort)
        except ClaudeContractError as exc:
            return _fail("invalid_invocation", f"Refusing to build a Claude dispatch: {exc}")
        runner = self._runner
        if self._runner is run_process:
            # Native launch depends on the process runner only (see review R07).
            try:
                command = resolve_claude_command()
            except ClaudeLauncherError as exc:
                return _fail("missing_binary", str(exc))
            runner = resolved_runner(self._runner, lambda: command, "claude")
        probes = []
        for argv in (["claude", "--version"], ["claude", "--help"]):
            probe = runner(argv, cwd, timeout=deadline_seconds(), cancel=self._cancel,
                           artifact_dir=self._artifact_dir)
            if probe.error or probe.returncode != 0:
                return _fail(probe.error or "nonzero_exit",
                             f"Claude CLI probe '{' '.join(argv)}' failed; install or repair the CLI.",
                             probe.metadata())
            probes.append(probe.stdout)
        try:
            check_capabilities(*probes)
        except ClaudeContractError as exc:
            return _fail("missing_capability", f"Claude CLI capability check failed: {exc}")
        proc = runner(invocation.argv, invocation.cwd, stdin=invocation.stdin, env=invocation.env,
                      unset_env=invocation.unset_env, timeout=deadline_seconds(self._timeout, dispatch=True),
                      cancel=self._cancel, artifact_dir=self._artifact_dir)
        metadata = dict(proc.metadata())
        raw_log = process_feedback((proc.stdout or "") + (proc.stderr or ""), metadata)
        outcome = parse_result(proc.stdout, proc.stderr, proc.returncode, model=self._model,
                               process_error=proc.error)
        if not outcome.ok:
            error = "malformed_output" if outcome.error in _STRUCTURAL else (outcome.error or "malformed_output")
            # No valid completion: never capture a candidate diff.
            return _fail(error, raw_log, metadata)
        try:
            diff, files_changed = capture_diff(self._git_runner, invocation.cwd)
        except CaptureError as exc:
            return _fail("diff_capture", raw_log + f"\nGit diff capture failed: {exc}", metadata)
        # Only evidenced token fields; the CLI's dollar figure is a subscription
        # estimate, never provider-reported spend, so CLD cost stays unknown.
        token_usage = {k: v for k, v in outcome.usage.items()
                       if k in ("input", "output", "cache_read", "cache_write")}
        usage_raw = {**outcome.usage_raw, "cost_estimate_usd": outcome.cost_estimate,
                     "cost_source": "cli_estimate_subscription"}
        return ExecutorResult(ok=True, diff=diff, files_changed=files_changed, token_usage=token_usage,
                              usage_raw=usage_raw, raw_log=raw_log, process=metadata)


@lru_cache(maxsize=1)
def _preflight():
    """(command, auth status, problem) once per process; model-free."""
    try:
        command = resolve_claude_command()
    except ClaudeLauncherError as exc:
        return None, None, str(exc)

    def two_tuple(argv, cwd):
        result = run_process(argv, cwd, env=command.env, timeout=deadline_seconds())
        return (result.returncode if not result.error else -1), result.stdout

    status, problem = run_auth_preflight(two_tuple, command.path)
    if problem is None:
        version, help_text = (run_process([command.path, flag], ".", env=command.env,
                                          timeout=deadline_seconds()).stdout
                              for flag in ("--version", "--help"))
        try:
            check_capabilities(version, help_text)
        except ClaudeContractError as exc:
            problem = f"Claude CLI capability check failed: {exc}"
    return command, status, problem


def reset_preflight_cache():
    _preflight.cache_clear()


def _launch_problem():
    return _preflight()[2]


def _context_extra():
    status = _preflight()[1]
    return account_context(status) if status is not None else ""


def _cli_invocation():
    command = _preflight()[0]
    return [command.path] if command is not None else ["claude"]


_HERE = Path(__file__).parent
PROVIDER = Provider(
    name="claude",
    make_executor=lambda **kwargs: ClaudeExecutor(**kwargs),
    catalog=(),
    default_workhorse="",  # Exact model selection is mandatory.
    list_models=list_models,  # Curated advisory menu; admission remains independent.
    account_stats=None,
    account_block=None,
    # Lambdas resolve module globals at call time so tests can patch _preflight.
    cli_invocation=lambda: _cli_invocation(),
    context_env=("CLAUDE_CLI_CMD", "CLAUDE_CONFIG_DIR", "ANTHROPIC_*"),
    context_extra=lambda: _context_extra(),
    launch_problem=lambda: _launch_problem(),
    skill_fragment=(_HERE / "SKILL.fragment.md").read_text(encoding="utf-8"),
    setup_notes=(_HERE / "setup.md").read_text(encoding="utf-8"),
)
register_provider(PROVIDER)
