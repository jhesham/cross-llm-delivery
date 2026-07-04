"""Cursor provider plugin -- single source of truth for the Cursor executor.

CursorExecutor, parse_cursor_usage, _cursor_invocation, _default_runner, and
resolve_composer_default are ALL defined here.  ``cld.executors.cursor`` is a thin
re-export shim that imports every name from this module so existing callers
continue to work unchanged.  Do not duplicate logic in the shim.

Invocation form (headless):
    [<node>, <version>/index.js] -p "<prompt>" --output-format json --workspace <cwd>
                                  --model <model> --force --trust

On Windows the .cmd shim mangles long prompts; the executor instead invokes the bundled
Node entrypoint directly: lexically-latest <LOCALAPPDATA>/cursor-agent/versions/<v>/index.js,
using the bundled node.exe in the same dir if present, else "node". Override with
CURSOR_AGENT_CMD (returns [override]). Non-Windows: ["cursor-agent"].

--force (auto-approve writes) + --trust (skip workspace-trust prompt) are REQUIRED
for headless operation. NEVER invoke bare (bare = interactive TUI that hangs).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Callable, List, Tuple

from cld.executors._capture import capture_diff
from cld.executors.base import ExecutorResult, SliceTask
from cld.models import ModelInfo
from cld.providers_api import Provider, register_provider

# runner(args, cwd) -> (returncode, stdout_or_combined_output)
Runner = Callable[[list[str], str], tuple[int, str]]

DEFAULT_MODEL = "composer-2.5"


def _default_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Real subprocess runner. Direct-node cursor-agent needs CURSOR_INVOKED_AS set and
    stdin closed. utf-8/replace; stderr merged on failure for raw_log."""
    env = {**os.environ, "CURSOR_INVOKED_AS": "cursor-agent"}
    # TLS-interception fix: cursor's BUNDLED node uses its own CA store, so behind a
    # TLS-intercepting proxy / AV MITM (e.g. Norton) it can't verify the Cursor API cert
    # and the agent writes NOTHING (a silent empty-diff failure). `--use-system-ca` makes
    # node trust the OS store (where the interceptor's root lives). Gate it to the bundled
    # node only: it's >=22 (cursor ships v24.x) and supports the flag; a bare system-`node`
    # fallback may be older and would reject an unknown NODE_OPTIONS flag. (git commands run
    # through this same runner are unaffected — they ignore NODE_OPTIONS anyway.)
    if args and os.path.isabs(args[0]) and "node" in os.path.basename(args[0]).lower():
        opts = env.get("NODE_OPTIONS", "")
        if "--use-system-ca" not in opts:
            env["NODE_OPTIONS"] = (opts + " --use-system-ca").strip()
    proc = subprocess.run(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return (proc.returncode, out)


def _cursor_invocation() -> list[str]:
    """Argv prefix to launch cursor-agent. CURSOR_AGENT_CMD overrides (returns [override]).
    On Windows the .cmd shim mangles long prompts, so invoke the bundled Node entrypoint
    directly: [<node>, <version>/index.js]. Falls back to ['cursor-agent']."""
    override = os.environ.get("CURSOR_AGENT_CMD")
    if override:
        return [override]
    if os.name == "nt":
        base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "cursor-agent", "versions")
        try:
            versions = sorted((d for d in os.listdir(base)
                               if os.path.isdir(os.path.join(base, d))), reverse=True)
        except OSError:
            versions = []
        for v in versions:
            vdir = os.path.join(base, v)
            index_js = os.path.join(vdir, "index.js")
            if os.path.exists(index_js):
                bundled = os.path.join(vdir, "node.exe")
                node = bundled if os.path.exists(bundled) else "node"
                return [node, index_js]
    return ["cursor-agent"]


def parse_cursor_usage(raw_json: str) -> dict[str, int]:
    """Parse Cursor JSON usage statistics.

    Cursor emits a single JSON object (not JSONL) on success:
      {"type":"result","subtype":"success","is_error":false,
       "usage":{"inputTokens":N,"outputTokens":M,...}}
    Returns {} on unparseable/empty/missing usage key.
    """
    try:
        data = json.loads(raw_json)
        if not isinstance(data, dict):
            return {}
        usage_data = data.get("usage")
        if not isinstance(usage_data, dict):
            return {}

        mapping = {
            "inputTokens": "input",
            "outputTokens": "output",
            "cacheReadTokens": "cache_read",
            "cacheWriteTokens": "cache_write",
        }

        result = {}
        for k, v in usage_data.items():
            if k in mapping and isinstance(v, int):
                result[mapping[k]] = v

        if "input" in result or "output" in result:
            result["total"] = result.get("input", 0) + result.get("output", 0)

        return result
    except Exception:
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
        argv = [*_cursor_invocation(), "-p", prompt, "--output-format", "json",
                "--workspace", cwd, "--model", model_id, "--force", "--trust"]
        rc, raw = self._runner(argv, cwd)
        if rc != 0:
            return ExecutorResult(ok=False, diff="", raw_log=raw)
        token_usage = parse_cursor_usage(raw)
        diff, files_changed = capture_diff(self._runner, cwd)
        return ExecutorResult(ok=True, diff=diff, files_changed=files_changed,
                              token_usage=token_usage, raw_log=raw)


# ---------------------------------------------------------------------------
# Provider-level helpers (moved from cld.models and run_delivery.py)
# ---------------------------------------------------------------------------

def list_cursor_models(runner: Callable[[List[str], str], Tuple[int, str]]) -> List[Tuple[str, str]]:
    """List available Cursor model ids via `cursor-agent --list-models`.

    Returns list of (id, label) tuples; degrades to [] on any failure.
    """
    try:
        rc, out = runner(["cursor-agent", "--list-models"], ".")
    except OSError:
        return []
    if rc != 0:
        return []

    models = []
    for line in out.splitlines():
        line = line.strip()
        if not line or " - " not in line:
            continue
        id_part, label_part = line.split(" - ", 1)
        id_part = id_part.strip()
        label_part = label_part.strip()
        if id_part == "auto":
            continue
        models.append((id_part, label_part))
    return models


def resolve_composer_default(runner: Callable[[List[str], str], Tuple[int, str]]) -> str:
    """Resolve the current Cursor Composer model id via --list-models.

    Prefers the model marked (current), then (default), then the highest
    version number. Fallback: 'composer-2.5'.
    """
    fallback = "composer-2.5"
    try:
        models = list_cursor_models(runner)
        composers = [(mid, label) for mid, label in models if mid.startswith("composer")]
        if not composers:
            return fallback

        for mid, label in composers:
            if "(current)" in label:
                return mid

        for mid, label in composers:
            if "(default)" in label:
                return mid

        max_ver = -1.0
        max_id = fallback
        found_version = False
        for mid, label in composers:
            if mid.startswith("composer-"):
                ver_str = mid[len("composer-"):].split("-")[0]
                try:
                    ver = float(ver_str)
                    if ver > max_ver:
                        max_ver = ver
                        max_id = mid
                        found_version = True
                except ValueError:
                    pass

        if found_version:
            return max_id
        return fallback
    except Exception:
        return fallback


def list_models(runner: Callable[[List[str], str], Tuple[int, str]]) -> List[str]:
    """List available Cursor model ids as a list of id strings.

    Wraps list_cursor_models and maps (id, label) -> id. Degrades to [] on
    any failure -- nonzero exit OR CLI not on PATH -- so the picker can fall
    back gracefully.
    """
    return [mid for mid, _label in list_cursor_models(runner)]


def account_stats() -> str:
    """Shell `cursor-agent about` and return raw text output.

    Cursor exposes no headless token/cost metric; `about` (tier + default model)
    is the only account signal. Timeout-guarded; returns "" on any failure.
    """
    invocation = _cursor_invocation()
    try:
        proc = subprocess.run([*invocation, "about"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
        return proc.stdout or ""
    except Exception:
        return ""


def account_block(cursor_about: dict) -> list:
    """Return the Cursor account block lines.

    cursor_about is the dict from cld.usage.parse_cursor_about().
    """
    tier = cursor_about.get("tier", "?")
    model = cursor_about.get("model", "?")
    return [
        "## Cursor account",
        f"Tier: {tier}   Default model: {model}",
        "Token/cost totals are server-side - run /usage in the Cursor TUI or see cursor.com.",
    ]


def account_section() -> list:
    """Self-contained account section: shell cursor-agent about + parse + render.

    Called by render_usage_table via the registry so the engine stays provider-blind.
    Returns [] on any error (degrades gracefully).
    """
    from cld.usage import parse_cursor_about  # local import: avoids circular at module level
    try:
        raw = account_stats()
        about = parse_cursor_about(raw)
        return account_block(about)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Catalog: cursor:composer-2.5 ModelInfo entry
# ---------------------------------------------------------------------------

_CURSOR_CATALOG = (
    ModelInfo(
        id="cursor:composer-2.5",
        provider="cursor",
        cost_class="cheap-metered",
        capability_class="heavy",
        headless_status="verified",
        rework_risk="low",
        note="Cursor's cost-optimized Composer; direct-node dispatch live-validated 2026-06-22",
        tier="workhorse",
    ),
)

# ---------------------------------------------------------------------------
# Provider registration
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent

_SKILL_FRAGMENT = (_HERE / "SKILL.fragment.md").read_text(encoding="utf-8")
_SETUP_NOTES = (_HERE / "setup.md").read_text(encoding="utf-8")

PROVIDER = Provider(
    name="cursor",
    make_executor=lambda **k: CursorExecutor(**k),
    catalog=_CURSOR_CATALOG,
    default_workhorse="cursor:composer-2.5",
    list_models=list_models,
    account_stats=account_stats,
    account_block=account_block,
    account_section=account_section,
    skill_fragment=_SKILL_FRAGMENT,
    setup_notes=_SETUP_NOTES,
)

register_provider(PROVIDER)
