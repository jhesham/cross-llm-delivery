"""Gemini provider plugin — registers the gemini executor with cld.providers_api.

GeminiExecutor is defined here (moved from cld.executors.gemini); the thin
re-export shim in cld.executors.gemini keeps existing import paths working
during migration (removed in Task 7 when the old paths are dropped).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Callable

from cld.executors._capture import capture_diff
from cld.executors.base import ExecutorResult, SliceTask
from cld.models import ModelInfo
from cld.providers_api import Provider, register_provider

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


# ---------------------------------------------------------------------------
# Provider registration
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent

_SKILL_FRAGMENT = (_HERE / "SKILL.fragment.md").read_text(encoding="utf-8")
_SETUP_NOTES = (_HERE / "setup.md").read_text(encoding="utf-8")

_GEMINI_MODEL_INFO = ModelInfo(
    id="gemini:gemini-3.1-pro-preview",
    provider="gemini",
    cost_class="flat",
    capability_class="workhorse",
    headless_status="revalidate",
    rework_risk="low",
    note="CLI deprecated 2026-06-21; superseded by antigravity. Historical adapter.",
    tier="workhorse",
)

PROVIDER = Provider(
    name="gemini",
    make_executor=lambda **k: GeminiExecutor(**k),
    catalog=(_GEMINI_MODEL_INFO,),
    default_workhorse="gemini:gemini-3.1-pro-preview",
    list_models=lambda runner: [],
    account_stats=None,
    account_block=None,
    skill_fragment=_SKILL_FRAGMENT,
    setup_notes=_SETUP_NOTES,
)

register_provider(PROVIDER)
