"""OpenCode provider plugin -- single source of truth for the OpenCode executor.

OpenCodeExecutor, parse_opencode_usage, _oc_cmd, _default_runner, and
_has_step_finish are ALL defined here.  ``cld.executors.opencode`` is a thin
re-export shim that imports every name from this module so existing callers
continue to work unchanged.  Do not duplicate logic in the shim.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Tuple

from cld.executors._capture import capture_diff
from cld.executors.base import ExecutorResult, SliceTask
from cld.models import ModelInfo
from cld.providers_api import Provider, register_provider

# runner(args, cwd) -> (returncode, stdout_or_combined_output)
Runner = Callable[[list[str], str], tuple[int, str]]

DEFAULT_MODEL = "opencode/deepseek-v4-flash-free"


def _default_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Real subprocess runner. stderr is merged into stdout on failure so the
    error text is captured in raw_log. Decodes utf-8 with replacement: model
    output can contain bytes invalid in the Windows locale codec (live kimi-k2.6
    validation emitted 0x90 and crashed the cp1252 reader thread).

    stdin=DEVNULL is REQUIRED, not cosmetic: opencode.exe invoked directly (the
    long-prompt path, no .cmd shim) BLOCKS forever reading an inherited stdin and
    emits zero output -- a live hang reproduced with gemini-3.1-pro (160s, nothing
    written) that vanished the instant stdin was closed. Detaching stdin makes the
    dispatch deterministic."""
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          stdin=subprocess.DEVNULL)
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return (proc.returncode, out)


def _oc_cmd() -> str:
    """The opencode CLI command, overridable via OPENCODE_CLI_CMD.

    Windows BUG fix (found live): the npm `opencode.cmd` shim runs via `cmd.exe /c`,
    which MANGLES a long multi-line prompt passed as a positional arg -- the dispatch
    silently falls back to interactive mode and emits no step_finish. The real
    `opencode.exe` (invoked directly by subprocess, no shell) handles the argv
    correctly, so on Windows we resolve the real exe behind the shim
    (`<npm-prefix>/node_modules/opencode-ai/bin/opencode.exe`) and use it. If it can't
    be located we fall back to the `.cmd` shim (fine for short prompts).
    """
    override = os.environ.get("OPENCODE_CLI_CMD")
    if override:
        return override
    if os.name != "nt":
        return "opencode"
    shim = shutil.which("opencode.cmd")
    if shim:
        exe = os.path.join(os.path.dirname(shim),
                           "node_modules", "opencode-ai", "bin", "opencode.exe")
        if os.path.exists(exe):
            return exe
    return "opencode.cmd"


def _has_step_finish(raw: str) -> bool:
    """True if the output contains at least one step_finish JSONL event -- the
    signature of a real, non-attached `--format json` dispatch."""
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if isinstance(d, dict) and d.get("type") == "step_finish":
            return True
    return False


def parse_opencode_usage(raw_json: str) -> dict[str, int]:
    usage: dict[str, int] = {}
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
                # opencode reports a per-step dollar cost on the step_finish part;
                # accumulate it so dispatch_end / the by-model rollup can show real $.
                cost = part.get("cost")
                if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                    usage["cost"] = usage.get("cost", 0) + cost
    return usage


class OpenCodeExecutor:
    """Executor implementation backed by the OpenCode CLI."""

    def __init__(self, *, runner: Runner = _default_runner, model: str = DEFAULT_MODEL,
                 variant: str | None = None, effort: str | None = None):
        self._runner = runner
        self._model = model
        self._variant = variant
        self._effort = effort

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

    def _build_dispatch(self, prompt: str, cwd: str) -> list[str]:
        """Argv for a plain headless run. The runner sets cwd=the target repo, and
        --dir names it too; a clean test confirmed this isolates correctly (no drift)."""
        dispatch = [
            _oc_cmd(),
            "run",
            prompt,
            "-m",
            self._model,
            "--format",
            "json",
            "--dir",
            cwd,
        ]
        variant = self._variant or self._effort
        if variant:
            dispatch += ["--variant", variant]
        # The default `build` agent treats writes outside its allowlist as
        # external_directory -> "ask"; headless can't answer, silently blocking
        # writes. Safe to auto-approve: isolated worktree, diff judged before merge.
        dispatch.append("--dangerously-skip-permissions")
        # Bare --port forces a fresh local server so the run can't join a stray
        # session. MUST be last: with no value it takes a random port (swallows nothing).
        dispatch.append("--port")
        return dispatch

    def run(self, task: SliceTask, workdir: Path, feedback: str | None = None) -> ExecutorResult:
        cwd = str(workdir)
        prompt = self._build_prompt(task, feedback)
        dispatch = self._build_dispatch(prompt, cwd)
        rc, raw = self._runner(dispatch, cwd)

        if rc != 0:
            return ExecutorResult(ok=False, diff="", raw_log=raw)
        if not _has_step_finish(raw):
            # No step_finish event = the dispatch produced no valid JSONL result
            # (e.g. a permission-blocked run that wrote nothing, or a format
            # regression). Never trust it; never capture a diff from it.
            return ExecutorResult(
                ok=False, diff="",
                raw_log=("DISPATCH GUARD: no step_finish JSONL event in output -- "
                         "the dispatch produced no valid result (permission block, "
                         "no work done, or wrong output format); refusing it.\n"
                         "--- original output ---\n" + raw),
            )

        token_usage = parse_opencode_usage(raw)
        diff, files_changed = capture_diff(self._runner, cwd)

        return ExecutorResult(
            ok=True,
            diff=diff,
            files_changed=files_changed,
            token_usage=token_usage,
            raw_log=raw,
        )


# ---------------------------------------------------------------------------
# Provider-level helpers (moved from cld.models and cld.usage)
# ---------------------------------------------------------------------------

def list_models(runner: Callable[[List[str], str], Tuple[int, str]]) -> List[str]:
    """List available OpenCode model ids via `opencode models`.

    Resolves the platform-correct command (Windows npm shim is `opencode.cmd`,
    overridable with OPENCODE_CLI_CMD). Degrades to [] on any failure -- nonzero
    exit OR the CLI not being on PATH (FileNotFoundError) -- so the picker can
    fall back to "Gemini only" instead of crashing.
    """
    oc_cmd = os.environ.get("OPENCODE_CLI_CMD") or (
        "opencode.cmd" if os.name == "nt" else "opencode"
    )
    try:
        rc, out = runner([oc_cmd, "models"], ".")
    except OSError:
        return []
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def account_stats() -> str:
    """Shell `opencode stats` and return the raw text output.

    Mirrors _opencode_stats_text from skill/scripts/run_delivery.py.
    Returns empty string on any failure.
    """
    oc = os.environ.get("OPENCODE_CLI_CMD") or ("opencode.cmd" if os.name == "nt" else "opencode")
    try:
        proc = subprocess.run([oc, "stats"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
        return proc.stdout or ""
    except Exception:
        return ""


def account_block(oc_stats: dict) -> list:
    """Return the OpenCode account block lines.

    Mirrors opencode_account_block from cld.usage.
    """
    lines = ["## OpenCode account"]
    if "total_cost" in oc_stats:
        lines.append(f"Total cost: ${oc_stats['total_cost']}")
        if "input" in oc_stats:
            lines.append(f"Input: {oc_stats['input']}")
        if "output" in oc_stats:
            lines.append(f"Output: {oc_stats['output']}")
    else:
        lines.append("OpenCode stats unavailable")
    return lines


def account_section() -> list:
    """Self-contained account section: shell stats + parse + render.

    Called by render_usage_table via the registry so the engine stays provider-blind.
    Returns [] on any error (degrades gracefully).
    """
    from cld.usage import parse_opencode_stats  # local import: avoids circular at module level
    try:
        raw = account_stats()
        stats = parse_opencode_stats(raw)
        return account_block(stats)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Catalog: the seven opencode/* ModelInfo entries
# ---------------------------------------------------------------------------

_OPENCODE_CATALOG = (
    ModelInfo(
        id="opencode/deepseek-v4-flash-free",
        provider="opencode",
        cost_class="free",
        capability_class="quick",
        headless_status="untested",
        rework_risk="medium",
        note="cheap, validate before trusting",
        tier="quick",
    ),
    ModelInfo(
        id="opencode/deepseek-v4-pro",
        provider="opencode",
        cost_class="cheap-metered",
        capability_class="workhorse",
        headless_status="likely",
        rework_risk="low",
        note="solid choice",
        tier="workhorse",
    ),
    ModelInfo(
        id="opencode/gemini-3.1-pro",
        provider="opencode",
        cost_class="cheap-metered",
        capability_class="workhorse",
        headless_status="likely",
        rework_risk="low",
        note="same model as the flat-rate workhorse, routed through OpenCode (metered)",
        tier="workhorse",
    ),
    ModelInfo(
        id="opencode/kimi-k2.6",
        provider="opencode",
        cost_class="cheap-metered",
        capability_class="heavy",
        headless_status="untested",
        rework_risk="medium",
        note="strong model; never cleanly validated headless - validate before trusting",
        tier="workhorse",
    ),
    ModelInfo(
        id="opencode/kimi-k2.7-code",
        provider="opencode",
        cost_class="cheap-metered",
        capability_class="heavy",
        headless_status="untested",
        rework_risk="medium",
        note="Kimi K2.7 (code) via OpenCode/Zen gateway; the plain 'kimi-k2.7' id is stale. "
             "Validate before trusting headless (evidence store carries live status).",
        tier="workhorse",
    ),
    ModelInfo(
        id="opencode/claude-opus-4-8",
        provider="opencode",
        cost_class="premium-metered",
        capability_class="heavy",
        headless_status="likely",
        rework_risk="medium",
        note="top capability, bills real money",
        tier=None,
    ),
    ModelInfo(
        id="opencode/claude-sonnet-4-6",
        provider="opencode",
        cost_class="premium-metered",
        capability_class="heavy",
        headless_status="likely",
        rework_risk="low",
        note="capable Anthropic Sonnet via OpenCode; bills real money",
        tier=None,
    ),
)

# ---------------------------------------------------------------------------
# Provider registration
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent

_SKILL_FRAGMENT = (_HERE / "SKILL.fragment.md").read_text(encoding="utf-8")
_SETUP_NOTES = (_HERE / "setup.md").read_text(encoding="utf-8")

PROVIDER = Provider(
    name="opencode",
    make_executor=lambda **k: OpenCodeExecutor(**k),
    catalog=_OPENCODE_CATALOG,
    default_workhorse="opencode:opencode/deepseek-v4-pro",
    list_models=list_models,
    account_stats=account_stats,
    account_block=account_block,
    account_section=account_section,
    skill_fragment=_SKILL_FRAGMENT,
    setup_notes=_SETUP_NOTES,
)

register_provider(PROVIDER)
