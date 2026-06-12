"""OpenCodeExecutor — adapts the OpenCode CLI to the Executor protocol.

    opencode run "<prompt>" -m <provider/model> --format json --dir <wt>

Mirrors GeminiExecutor: build argv, run via the injected runner, parse OpenCode's
token usage, capture the diff via the shared capture_diff. Windows resolves
`opencode.cmd`; override with OPENCODE_CLI_CMD.

`--format json` emits JSONL (one event per line); parse_opencode_usage reads the
step_finish event(s). See docs/notes/opencode-cli-notes.md.
"""

import os
import subprocess
from pathlib import Path
from typing import Callable

from cld.executors._capture import capture_diff
from cld.executors.base import ExecutorResult, SliceTask

# runner(args, cwd) -> (returncode, stdout_or_combined_output)
Runner = Callable[[list[str], str], tuple[int, str]]

DEFAULT_MODEL = "opencode/deepseek-v4-flash-free"


def _default_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Real subprocess runner. stderr is merged into stdout on failure so the
    error text is captured in raw_log. Decodes utf-8 with replacement: model
    output can contain bytes invalid in the Windows locale codec (live kimi-k2.6
    validation emitted 0x90 and crashed the cp1252 reader thread)."""
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return (proc.returncode, out)


def parse_opencode_usage(raw_json: str) -> dict[str, int]:
    import json
    usage = {}
    if not raw_json:
        return usage
    for line in raw_json.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue
        if isinstance(data, dict) and data.get("type") == "step_finish":
            part = data.get("part")
            if isinstance(part, dict):
                tokens = part.get("tokens")
                if isinstance(tokens, dict):
                    for k, v in tokens.items():
                        if type(v) is int:
                            usage[k] = usage.get(k, 0) + v
    return usage


class OpenCodeExecutor:
    """Executor implementation backed by the OpenCode CLI."""

    def __init__(self, *, runner: Runner = _default_runner, model: str = DEFAULT_MODEL,
                 variant: str | None = None):
        self._runner = runner
        self._model = model
        self._variant = variant

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
            prompt += (
                f"\n\nYour previous attempt did not pass. {feedback}\n"
                f"Address this specifically before trying again."
            )
        return prompt

    def run(self, task: SliceTask, workdir: Path, feedback: str | None = None) -> ExecutorResult:
        cwd = str(workdir)
        prompt = self._build_prompt(task, feedback)

        # Resolve the CLI command per-platform (Windows npm shim is opencode.cmd).
        oc_cmd = os.environ.get("OPENCODE_CLI_CMD") or (
            "opencode.cmd" if os.name == "nt" else "opencode"
        )
        dispatch = [
            oc_cmd,
            "run",
            prompt,
            "-m",
            self._model,
            "--format",
            "json",
            "--dir",
            cwd,
        ]
        if self._variant:
            dispatch += ["--variant", self._variant]

        rc, raw = self._runner(dispatch, cwd)

        if rc != 0:
            return ExecutorResult(ok=False, diff="", raw_log=raw)

        token_usage = parse_opencode_usage(raw)
        diff, files_changed = capture_diff(self._runner, cwd)

        return ExecutorResult(
            ok=True,
            diff=diff,
            files_changed=files_changed,
            token_usage=token_usage,
            raw_log=raw,
        )
