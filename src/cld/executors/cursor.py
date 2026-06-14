"""CursorExecutor — adapts the cursor-agent CLI to the Executor protocol.

    cursor-agent -p "<prompt>" --output-format json --workspace <cwd>
                 --model <model> --force --trust

Mirrors OpenCodeExecutor: build argv, run via the injected runner, parse cursor's
token usage (stub), capture the diff via the shared capture_diff.

On Windows the top-level launcher shim is broken; we resolve the lexically-latest
versioned cursor-agent.cmd under <LOCALAPPDATA>/cursor-agent/versions/.
Override with CURSOR_AGENT_CMD.

--force (auto-approve writes) + --trust (skip workspace-trust prompt) are REQUIRED
for headless operation. NEVER invoke bare (bare = interactive TUI that hangs).
"""

import os
import subprocess
from pathlib import Path
from typing import Callable

from cld.executors._capture import capture_diff
from cld.executors.base import ExecutorResult, SliceTask

# runner(args, cwd) -> (returncode, stdout_or_combined_output)
Runner = Callable[[list[str], str], tuple[int, str]]

DEFAULT_MODEL = "composer-2.5"


def _default_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Real subprocess runner. stderr is merged into stdout on failure so the
    error text is captured in raw_log. Decodes utf-8 with replacement: model
    output can contain bytes invalid in the Windows locale codec."""
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return (proc.returncode, out)


def _cursor_cmd() -> str:
    """Resolve the cursor-agent command. CURSOR_AGENT_CMD overrides. On Windows the
    top-level shim is broken, so resolve the lexically-latest versioned cursor-agent.cmd
    under <LOCALAPPDATA>/cursor-agent/versions/. Fallback: bare 'cursor-agent'."""
    override = os.environ.get("CURSOR_AGENT_CMD")
    if override:
        return override
    if os.name == "nt":
        base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "cursor-agent", "versions")
        try:
            versions = sorted((d for d in os.listdir(base)
                               if os.path.isdir(os.path.join(base, d))), reverse=True)
            for v in versions:
                cand = os.path.join(base, v, "cursor-agent.cmd")
                if os.path.exists(cand):
                    return cand
        except OSError:
            pass
    return "cursor-agent"


def parse_cursor_usage(raw_json: str) -> dict:
    """Placeholder — replaced in a later task against the real fixture. {} for now."""
    return {}


class CursorExecutor:
    """Executor implementation backed by the cursor-agent CLI."""

    def __init__(self, *, runner: Runner = _default_runner, model: str = DEFAULT_MODEL,
                 effort: str | None = None, timeout: int = 600):
        self._runner = runner
        self._model = model
        self._effort = effort
        self._timeout = timeout

    def _build_prompt(self, task: SliceTask, feedback: str | None = None) -> str:
        allowed = ", ".join(task.files)
        prompt = (
            f"Implement the following so that the acceptance tests pass.\n\n"
            f"{task.brief}\n\n"
            f"You may only create/modify these files: {allowed}\n"
            f"Acceptance tests: {task.acceptance_test_path}\n"
            f"Do not edit the test file. Run pytest yourself and iterate until green."
        )
        if feedback:
            prompt += (f"\n\nYour previous attempt did not pass. {feedback}\n"
                       f"Address this specifically before trying again.")
        return prompt

    def run(self, task: SliceTask, workdir: Path, feedback: str | None = None) -> ExecutorResult:
        cwd = str(workdir)
        prompt = self._build_prompt(task, feedback)
        model_id = f"{self._model}-{self._effort}" if self._effort else self._model
        argv = [_cursor_cmd(), "-p", prompt, "--output-format", "json",
                "--workspace", cwd, "--model", model_id, "--force", "--trust"]
        rc, raw = self._runner(argv, cwd)
        if rc != 0:
            return ExecutorResult(ok=False, diff="", raw_log=raw)
        token_usage = parse_cursor_usage(raw)
        diff, files_changed = capture_diff(self._runner, cwd)
        return ExecutorResult(ok=True, diff=diff, files_changed=files_changed,
                              token_usage=token_usage, raw_log=raw)
