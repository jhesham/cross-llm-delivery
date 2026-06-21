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


# ---------------------------------------------------------------------------
# Provider registration (minimal stub for Task 1; full executor in Task 2)
# ---------------------------------------------------------------------------

from cld.models import ModelInfo
from cld.providers_api import Provider, register_provider

_HERE = Path(__file__).parent
_SKILL_FRAGMENT = (_HERE / "SKILL.fragment.md").read_text(encoding="utf-8")
_SETUP_NOTES = (_HERE / "setup.md").read_text(encoding="utf-8")

_ANTIGRAVITY_MODEL_INFO = ModelInfo(
    id="antigravity:agy-claude",
    provider="antigravity",
    cost_class="flat",
    capability_class="workhorse",
    headless_status="untested",
    rework_risk="medium",
    note="Antigravity executor (Task 2 in progress)",
    tier="workhorse",
)

PROVIDER = Provider(
    name="antigravity",
    make_executor=lambda **k: None,  # Placeholder; full executor in Task 2
    catalog=(_ANTIGRAVITY_MODEL_INFO,),
    default_workhorse="antigravity:agy-claude",
    list_models=lambda runner: [],
    account_stats=None,
    account_block=None,
    skill_fragment=_SKILL_FRAGMENT,
    setup_notes=_SETUP_NOTES,
)

register_provider(PROVIDER)
