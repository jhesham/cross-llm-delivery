"""GeminiExecutor — adapts the Gemini CLI to the Executor protocol.

Wraps the locked headless invocation (verified on this machine, Phase 0 +
four gate dispatches):

    GEMINI_CLI_TRUST_WORKSPACE=true gemini -p "<task>" -m <model> \
        --yolo --skip-trust -o json

Parses `stats.models.*.tokens` from the JSON output into ExecutorResult.
token_usage, and captures the produced change as a unified diff via git.

All process execution goes through an injected `runner` callable so the class
is unit-testable without touching the network or the real CLI. The default
runner uses subprocess; tests pass a fake.

Note on invocation form: we use `--yolo --skip-trust` (the form with a confirmed
successful run across Phase 0 + all four gate dispatches), not the `--approval-mode
auto_edit` variant suggested in docs/notes/gemini-cli.md — that variant was a
recommendation, never the proven path.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Callable

from cld.executors._capture import capture_diff
from cld.executors.base import ExecutorResult, SliceTask

# runner(args, cwd) -> (returncode, stdout_or_combined_output)
Runner = Callable[[list[str], str], tuple[int, str]]

DEFAULT_MODEL = "gemini-3.1-pro-preview"


def _default_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Real subprocess runner. stderr is merged into stdout so the raw_log /
    error text is captured (the CLI emits harmless warnings on stderr)."""
    env = {**os.environ, "GEMINI_CLI_TRUST_WORKSPACE": "true"}
    proc = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",  # model output may not be valid in the locale codec
    )
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return (proc.returncode, out)


def parse_token_usage(raw_json: str) -> dict[str, int]:
    """Sum stats.models.*.tokens into a flat usage dict.

    Maps `candidates` -> `output` (the CLI's name for generated tokens).
    Returns {} on unparseable input rather than raising.
    """
    try:
        data = json.loads(raw_json)
    except (ValueError, TypeError):
        return {}

    models = data.get("stats", {}).get("models", {})
    if not models:
        return {}

    usage: dict[str, int] = {}
    for model in models.values():
        toks = model.get("tokens", {})
        for key, val in toks.items():
            if not isinstance(val, int):
                continue
            name = "output" if key == "candidates" else key
            usage[name] = usage.get(name, 0) + val
    return usage


class GeminiExecutor:
    """Executor implementation backed by the Gemini CLI."""

    def __init__(self, *, runner: Runner = _default_runner, model: str = DEFAULT_MODEL,
                 effort: str | None = None):
        # effort: accepted for a uniform executor interface; gemini has no effort axis
        self._runner = runner
        self._model = model

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

        # Resolve the CLI command per-platform. On Windows the npm shim is
        # `gemini.cmd`, which subprocess (without shell=True) cannot find under
        # the bare name `gemini`. Allow an explicit override via GEMINI_CLI_CMD.
        gemini_cmd = os.environ.get("GEMINI_CLI_CMD") or (
            "gemini.cmd" if os.name == "nt" else "gemini"
        )
        dispatch = [
            gemini_cmd,
            "-p",
            prompt,
            "-m",
            self._model,
            "--yolo",
            "--skip-trust",
            "-o",
            "json",
        ]
        rc, raw = self._runner(dispatch, cwd)

        if rc != 0:
            return ExecutorResult(ok=False, diff="", raw_log=raw)

        token_usage = parse_token_usage(raw)

        # Capture what changed via git (also through the injected runner).
        diff, files_changed = capture_diff(self._runner, cwd)

        return ExecutorResult(
            ok=True,
            diff=diff,
            files_changed=files_changed,
            token_usage=token_usage,
            raw_log=raw,
        )
