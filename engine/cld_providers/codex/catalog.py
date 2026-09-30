"""Local advisory Codex picker metadata. No refresh, inference or entitlement claim."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from cld.process import deadline_seconds, run_process
from .launcher import CodexLauncherError, resolve_codex_command

_EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")


@dataclass(frozen=True)
class CodexModel:
    id: str
    label: str
    efforts: tuple[str, ...]


def _default_runner(argv, cwd):
    # Unresolvable CLI: keep the logical name; launching then fails as a missing
    # binary and discovery yields [], exactly as before the launcher existed.
    try:
        command = resolve_codex_command()
    except CodexLauncherError:
        command = None
    command_argv = list(argv)
    if command is not None and command_argv and command_argv[0] == "codex":
        command_argv[0] = command.path
    extra = {"env": command.env} if command is not None and command.env else {}
    result = run_process(command_argv, cwd, timeout=deadline_seconds(), **extra)
    return result.returncode, result.stdout if not result.error else ""


def list_codex_models(runner=_default_runner) -> list[CodexModel]:
    """Read only the installed binary's bundled catalog; old/missing CLI yields [].

    Hidden entries, malformed IDs and efforts CLD cannot dispatch are excluded.
    This list is not account validation or a production default. Explicit
    --executor IDs remain usable when this optional command is absent.
    """
    try:
        rc, raw = runner(["codex", "debug", "models", "--bundled"], Path.cwd())
        if rc != 0:
            return []
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            return []
    except (CodexLauncherError, OSError, ValueError, TypeError):
        return []
    out, seen = [], set()
    for row in data["models"]:
        if not isinstance(row, dict) or row.get("visibility") != "list":
            continue
        id = row.get("slug")
        if not isinstance(id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", id) or id in seen:
            continue
        levels = row.get("supported_reasoning_levels")
        if not isinstance(levels, list):
            continue
        supported = [level.get("effort") for level in levels if isinstance(level, dict)]
        efforts = tuple(e for e in _EFFORTS if e in supported)
        if not efforts:
            continue
        label = row.get("display_name")
        if not isinstance(label, str) or not label.strip() or any(ord(c) < 32 for c in label):
            label = id
        out.append(CodexModel(id, label, efforts))
        seen.add(id)
    return out


def list_models(runner):
    """Provider API projection; no static catalog or default."""
    return [model.id for model in list_codex_models(runner=runner)]
