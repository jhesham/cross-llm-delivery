"""Antigravity provider plugin — the `agy` CLI executor.

`agy` returns the model reply and token usage as JSON on stdout. If no JSON
result is available, the executor falls back to the transcript under a POSIX path
(`/Users/<name>/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/
transcript.jsonl`). On Windows, a leading-/ path resolves to the current
drive's root, so dispatch uses the SystemDrive to make transcript lookup work.
POSIX dispatch uses the native home directory.
See docs/notes/antigravity-cli-notes.md.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path


def _dispatch_cwd() -> str:
    """Choose a cwd where agy's POSIX-style transcript path resolves."""
    home = Path.home()
    if os.name != "nt":
        return str(home)
    sysdrive = os.environ.get("SystemDrive", "C:")
    if (home.drive or "").upper() != sysdrive.upper():
        return str(Path(sysdrive + os.sep) / "Users" / home.name)
    return str(home)


_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _parse_conversation_id(log_text: str) -> str | None:
    """The per-dispatch conversation id is the most frequently-occurring UUID in the log."""
    ids = _UUID_RE.findall(log_text or "")
    if not ids:
        return None
    return Counter(ids).most_common(1)[0][0]


def _transcript_path(home: str, conversation_id: str) -> str:
    return os.path.join(home, ".gemini", "antigravity-cli", "brain", conversation_id,
                        ".system_generated", "logs", "transcript.jsonl")


def _extract_model_reply(transcript_text: str) -> str | None:
    """Join the `content` of every JSONL step whose source is MODEL; None if none."""
    replies = []
    for line in (transcript_text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("source") == "MODEL" and obj.get("content"):
            replies.append(str(obj["content"]))
    return "\n".join(replies) if replies else None


from typing import Callable

from cld.executors._capture import capture_diff
from cld.executors.base import ExecutorResult, SliceTask
from cld.process import (run_process, dispatch as run_dispatch, feedback as process_feedback,
                         artifact_file, executor_depth_blocked)

Runner = Callable[[list[str], str], tuple[int, str]]

DEFAULT_MODEL = "Gemini 4 Argon (High)"


def _agy_cmd() -> str:
    """Resolve AGY_CMD, then PATH, then the Windows install path, then 'agy'."""
    override = os.environ.get("AGY_CMD")
    if override:
        return override
    on_path = shutil.which("agy")
    if on_path:
        return on_path
    if os.name == "nt":
        cand = os.path.join(os.environ.get("LOCALAPPDATA", ""), "agy", "bin", "agy.exe")
        if os.path.exists(cand):
            return cand
    return "agy"


def _default_runner(args: list[str], cwd: str, **options):
    """Bounded probe by default; dispatch supplies its own deadline."""
    return run_process(args, cwd, **options)



class AntigravityExecutor:
    """Executor backed by the Antigravity CLI (`agy`)."""

    def __init__(self, *, runner: Runner = _default_runner, model: str = DEFAULT_MODEL,
                 effort: str | None = None, home: str | None = None, timeout: float | None = None,
                 cancel=None, artifact_dir=None):
        self._timeout, self._cancel, self._artifact_dir = timeout, cancel, artifact_dir
        self._runner = runner
        self._model = model
        self._effort = effort
        self._home = home or _dispatch_cwd()

    def _build_prompt(self, task: SliceTask, feedback: str | None = None) -> str:
        allowed = ", ".join(task.files)
        prompt = (
            f"You are an executor for exactly one CLD delivery slice. Do not invoke CLD, "
            f"any other LLM provider, or any dispatch tool; recursive delegation is prohibited.\n\n"
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

    def run(self, task: SliceTask, workdir, feedback: str | None = None) -> ExecutorResult:
        if executor_depth_blocked():
            return ExecutorResult(ok=False, diff="", files_changed=[],
                                  raw_log="Recursive dispatch blocked: CLD_EXECUTOR_DEPTH is already set; "
                                          "refusing to start another executor.",
                                  process={"error": "recursive_dispatch"})
        prompt = self._build_prompt(task, feedback)
        log_file = artifact_file(prefix="agy_", suffix=".log", artifact_dir=self._artifact_dir)
        dispatch = [
            _agy_cmd(), "-p", prompt, "--model", self._model,
            "--add-dir", str(workdir), "--dangerously-skip-permissions",
            "--log-file", log_file,
            "--output-format", "json",
        ]
        if self._effort:
            dispatch.extend(["--effort", self._effort])
        try:
            rc, raw, process = run_dispatch(self._runner, _default_runner, dispatch, self._home,
                timeout=self._timeout, cancel=self._cancel, artifact_dir=self._artifact_dir,
                env={"CLD_EXECUTOR_DEPTH": "1"})   # cwd = selected home
        except BaseException as exc:
            exc.provider_log_path = log_file
            raise
        process["provider_log_path"] = log_file

        reply = None
        result = None
        for line in (raw or "").splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and "status" in obj:
                result = obj
        # Usage agy reports is real consumption even when the dispatch failed.
        token_usage = {}
        usage = result.get("usage") if result is not None else None
        if isinstance(usage, dict):
            token_usage = {
                key: usage[source]
                for key, source in (("input", "input_tokens"), ("output", "output_tokens"),
                                    ("cache_read", "cache_read_tokens"), ("total", "total_tokens"))
                if type(usage.get(source)) is int
            }

        if rc != 0:
            return ExecutorResult(ok=False, diff="", raw_log=process_feedback(raw, process),
                                  token_usage=token_usage, process=process)

        if result is not None:
            if result["status"] != "SUCCESS":
                return ExecutorResult(
                    ok=False, diff="", token_usage=token_usage,
                    process={**process, "error": "agy_error"},
                    raw_log=process_feedback(str(result.get("error") or raw or ""), process))
            reply = result.get("response")
        else:
            try:
                log_text = Path(log_file).read_text(encoding="utf-8", errors="replace")
            except OSError:
                log_text = ""
            log_text = (raw or "") + "\n" + log_text      # raw carries it in tests; log file in prod

            conv = _parse_conversation_id(log_text)
            if conv:
                try:
                    transcript = Path(_transcript_path(self._home, conv)).read_bytes()
                    retained = Path(log_file).with_suffix(".transcript.jsonl")
                    retained.write_bytes(transcript)
                    process["transcript_path"] = str(retained)
                    reply = _extract_model_reply(transcript.decode("utf-8", errors="replace"))
                except OSError:
                    reply = None
        # A dispatch completed when agy reported SUCCESS (even with an empty reply, e.g.
        # it finished on a tool call or committed its work) or a transcript reply exists.
        # Anything else is a failed dispatch and never captures a diff. A completed
        # dispatch is judged by the candidate check against the dispatch base.
        if result is None and not reply:
            if os.name == "nt":
                transcript_hint = ("the agy dispatch must run with cwd on the SystemDrive "
                                   "so its POSIX-style transcript path resolves")
            else:
                transcript_hint = ("check that agy wrote its transcript under the selected home "
                                   f"({self._home})")
            return ExecutorResult(
                ok=False, diff="", process={**process, "error": "malformed_output"},
                raw_log=process_feedback(raw or "", process, 3500) + "\n[antigravity] no MODEL transcript found; "
                        + transcript_hint + " (see "
                        "docs/notes/antigravity-cli-notes.md)")
        diff, files_changed = capture_diff(self._runner, str(workdir))

        if not reply:
            reply = (raw or "") + "\n[antigravity] no closing reply; the candidate check decides"
        return ExecutorResult(ok=True, diff=diff, files_changed=files_changed,
                              token_usage=token_usage, raw_log=process_feedback(reply, process), process=process)



from cld.models import ModelInfo
from cld.providers_api import Provider, register_provider

_HERE = Path(__file__).parent
_SKILL_FRAGMENT = (_HERE / "SKILL.fragment.md").read_text(encoding="utf-8")
_SETUP_NOTES = (_HERE / "setup.md").read_text(encoding="utf-8")


def _m(label, capability_class, tier, headless_status, rework_risk, note):
    return ModelInfo(id=f"antigravity:{label}", provider="antigravity", cost_class="flat",
                     capability_class=capability_class, headless_status=headless_status,
                     rework_risk=rework_risk, note=note, tier=tier)


_CATALOG = (
    _m("Gemini 3.8 Flash (Low)",    "quick",     None,        "likely",   "low",
       "fast budget model; pin for trivial slices"),
    _m("Gemini 3.8 Flash (Medium)", "quick",     "quick",     "likely",   "low",
       "balanced budget workhorse; quick-tier auto-pick"),
    _m("Gemini 3.8 Flash (High)",   "quick",     None,        "likely",   "low",
       "budget model, more thinking; pin manually"),
    _m("Gemini 4 Argon (Low)",      "workhorse", None,        "likely",   "low",
       "Argon, lighter thinking; pin manually"),
    _m("Gemini 4 Argon (High)",     "workhorse", "workhorse", "verified", "low",
       "default workhorse; flat-rate via Antigravity"),
    _m("GPT-OSS 120B (Medium)",     "workhorse", None,        "untested", "medium",
       "open model; validate before relying on it"),
    _m("Claude Sonnet 5.5 (High)", "workhorse", None,         "likely",   "low",
       "strong workhorse; flat-rate via Antigravity; pin manually"),
    _m("Claude Opus 5.5 (High)",   "heavy",     None,         "likely",   "low",
       "premium reasoning; flat-rate via Antigravity; pin manually for hard slices"),
)

_IDS = [m.id.split(":", 1)[1] for m in _CATALOG]


def list_agy_models(runner: Runner) -> list[str]:
    """Discover labels from agy 1.5.1, falling back to the recorded catalog."""
    try:
        rc, raw = runner([_agy_cmd(), "models"], _dispatch_cwd())
        if rc == 0:
            labels = []
            for line in raw.splitlines():
                slug, sep, label = line.partition("\t")
                if sep and slug.strip() and label.strip():
                    labels.append(label)
            if labels:
                return labels
    except Exception:
        pass
    return list(_IDS)


PROVIDER = Provider(
    cli_invocation=lambda: [_agy_cmd()],
    context_env=("AGY_CMD",),
    name="antigravity",
    make_executor=lambda **k: AntigravityExecutor(**k),
    catalog=_CATALOG,
    default_workhorse="antigravity:Gemini 4 Argon (High)",
    list_models=list_agy_models,
    uncatalogued_cost_class="flat",
    account_stats=None,
    account_block=None,
    skill_fragment=_SKILL_FRAGMENT,
    setup_notes=_SETUP_NOTES,
)

register_provider(PROVIDER)
