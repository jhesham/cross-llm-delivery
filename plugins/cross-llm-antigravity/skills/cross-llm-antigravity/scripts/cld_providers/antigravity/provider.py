"""Antigravity provider plugin — the `agy` CLI executor.

Windows gotcha: `agy` writes the model reply to a transcript file under a POSIX
path (/Users/<name>/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/
transcript.jsonl). A leading-/ path resolves to the current drive's root on
Windows, so the dispatch must run with cwd on the C: drive. stdout is empty by
design — the reply lives in the transcript. See docs/notes/antigravity-cli-notes.md.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path


def _dispatch_cwd() -> str:
    """User home forced onto SystemDrive, so agy's POSIX transcript path resolves."""
    home = Path.home()
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


import subprocess
import tempfile
from typing import Callable

from cld.executors._capture import capture_diff
from cld.executors.base import ExecutorResult, SliceTask

Runner = Callable[[list[str], str], tuple[int, str]]

DEFAULT_MODEL = "Gemini 3.1 Pro (High)"


def _agy_cmd() -> str:
    """Resolve the agy executable. AGY_CMD overrides; else the known install path; else 'agy'."""
    override = os.environ.get("AGY_CMD")
    if override:
        return override
    if os.name == "nt":
        cand = os.path.join(os.environ.get("LOCALAPPDATA", ""), "agy", "bin", "agy.exe")
        if os.path.exists(cand):
            return cand
    return "agy"


def _default_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Real subprocess runner: stdin closed (agy waits on a TTY otherwise), utf-8/replace."""
    proc = subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return (proc.returncode, out)


class AntigravityExecutor:
    """Executor backed by the Antigravity CLI (`agy`)."""

    def __init__(self, *, runner: Runner = _default_runner, model: str = DEFAULT_MODEL,
                 effort: str | None = None, home: str | None = None):
        # effort accepted for a uniform interface; antigravity bakes effort into the model label
        self._runner = runner
        self._model = model
        self._home = home or _dispatch_cwd()

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

    def run(self, task: SliceTask, workdir, feedback: str | None = None) -> ExecutorResult:
        prompt = self._build_prompt(task, feedback)
        fd, log_file = tempfile.mkstemp(prefix="agy_", suffix=".log")
        os.close(fd)
        try:
            dispatch = [
                _agy_cmd(), "-p", prompt, "--model", self._model,
                "--add-dir", str(workdir), "--dangerously-skip-permissions",
                "--log-file", log_file,
            ]
            rc, raw = self._runner(dispatch, self._home)   # cwd = home on C:
            if rc != 0:
                return ExecutorResult(ok=False, diff="", raw_log=raw)

            try:
                log_text = Path(log_file).read_text(encoding="utf-8", errors="replace")
            except OSError:
                log_text = ""
            log_text = (raw or "") + "\n" + log_text       # raw carries it in tests; log file in prod

            reply = None
            conv = _parse_conversation_id(log_text)
            if conv:
                try:
                    reply = _extract_model_reply(
                        Path(_transcript_path(self._home, conv)).read_text(
                            encoding="utf-8", errors="replace"))
                except OSError:
                    reply = None
            if reply is None:
                return ExecutorResult(
                    ok=False, diff="",
                    raw_log=(raw or "") + "\n[antigravity] no MODEL transcript found; the agy "
                            "dispatch must run with cwd on the C: drive (see "
                            "docs/notes/antigravity-cli-notes.md)")

            diff, files_changed = capture_diff(self._runner, str(workdir))
            return ExecutorResult(ok=True, diff=diff, files_changed=files_changed,
                                  token_usage={}, raw_log=reply)
        finally:
            try:
                os.unlink(log_file)
            except OSError:
                pass


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
    _m("Gemini 3.5 Flash (Low)",    "quick",     None,        "likely",   "low",
       "fast budget model; pin for trivial slices"),
    _m("Gemini 3.5 Flash (Medium)", "quick",     "quick",     "likely",   "low",
       "balanced budget workhorse; quick-tier auto-pick"),
    _m("Gemini 3.5 Flash (High)",   "quick",     None,        "likely",   "low",
       "budget model, more thinking; pin manually"),
    _m("Gemini 3.1 Pro (Low)",      "workhorse", None,        "likely",   "low",
       "Pro, lighter thinking; pin manually"),
    _m("Gemini 3.1 Pro (High)",     "workhorse", "workhorse", "verified", "low",
       "default workhorse; flat-rate via Antigravity; live-validated 2026-06-22"),
    _m("GPT-OSS 120B (Medium)",     "workhorse", None,        "untested", "medium",
       "open model; validate before relying on it"),
    _m("Claude Sonnet 4.6 (Thinking)", "workhorse", None,     "likely",   "low",
       "strong workhorse; flat-rate via Antigravity; pin manually"),
    _m("Claude Opus 4.6 (Thinking)",   "heavy",     None,     "likely",   "low",
       "premium reasoning; flat-rate via Antigravity; pin manually for hard slices"),
)

_IDS = [m.id.split(":", 1)[1] for m in _CATALOG]

PROVIDER = Provider(
    name="antigravity",
    make_executor=lambda **k: AntigravityExecutor(**k),
    catalog=_CATALOG,
    default_workhorse="antigravity:Gemini 3.1 Pro (High)",
    list_models=lambda runner: list(_IDS),
    account_stats=None,
    account_block=None,
    skill_fragment=_SKILL_FRAGMENT,
    setup_notes=_SETUP_NOTES,
)

register_provider(PROVIDER)
