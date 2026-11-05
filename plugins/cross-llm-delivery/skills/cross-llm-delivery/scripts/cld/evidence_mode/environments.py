"""Load project environment declarations used by evidence mode."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Environment:
    """A configured execution environment."""

    name: str
    cls: Literal["sandbox", "real"]
    platform: str
    command: tuple[str, ...]
    read_only_expected: bool
    mcp_only: bool = False
    job_id_pattern: str | None = None


class EnvironmentError(ValueError):
    """Raised when a project environment declaration is invalid."""


def _field(entry: dict[str, object], name: str) -> object:
    if name not in entry:
        raise EnvironmentError(f"environment field '{name}' is required")
    return entry[name]


def _nonempty_string(entry: dict[str, object], name: str) -> str:
    value = _field(entry, name)
    if not isinstance(value, str) or not value.strip():
        raise EnvironmentError(f"environment field '{name}' must be a non-empty string")
    return value


def load_environments(repo: str | Path, path: str | Path | None = None) -> dict[str, Environment]:
    """Load and validate ``cld-environments.json`` from a repository.

    If the file does not exist, there are no configured environments.
    """

    source = Path(path) if path is not None else Path(repo) / "cld-environments.json"
    try:
        raw = source.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except UnicodeDecodeError as exc:
        raise EnvironmentError(f"invalid environment JSON encoding in '{source}': {exc}") from exc

    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EnvironmentError(f"invalid environment JSON in '{source}': {exc}") from exc

    if not isinstance(document, dict):
        raise EnvironmentError("environment file field 'environments' must be a list")
    entries = document.get("environments")
    if not isinstance(entries, list):
        raise EnvironmentError("environment file field 'environments' must be a list")

    environments: dict[str, Environment] = {}
    for index, entry in enumerate(entries):
        prefix = f"environments[{index}]"
        if not isinstance(entry, dict):
            raise EnvironmentError(f"{prefix} must be an object")

        name = _nonempty_string(entry, "name")
        if name in environments:
            raise EnvironmentError(f"duplicate environment name '{name}'")

        cls = _field(entry, "class")
        if cls not in ("sandbox", "real"):
            raise EnvironmentError("environment field 'class' must be 'sandbox' or 'real'")

        platform = _nonempty_string(entry, "platform")

        mcp_only = entry.get("mcp_only", False)
        if not isinstance(mcp_only, bool):
            raise EnvironmentError("environment field 'mcp_only' must be a boolean")

        command_value = entry.get("command", []) if mcp_only else _field(entry, "command")
        if not isinstance(command_value, list) or any(not isinstance(arg, str) for arg in command_value):
            raise EnvironmentError("environment field 'command' must be a list of strings")
        command = tuple(command_value)
        if not command and not mcp_only:
            raise EnvironmentError("environment field 'command' must not be empty unless 'mcp_only' is true")

        read_only_expected = _field(entry, "read_only_expected")
        if not isinstance(read_only_expected, bool):
            raise EnvironmentError("environment field 'read_only_expected' must be a boolean")
        if cls == "real" and read_only_expected is not True:
            raise EnvironmentError("environment field 'read_only_expected' must be true for real environments")

        job_id_pattern = entry.get("job_id_pattern")
        if job_id_pattern is not None and not isinstance(job_id_pattern, str):
            raise EnvironmentError("environment field 'job_id_pattern' must be a string or null")

        environments[name] = Environment(
            name=name,
            cls=cls,
            platform=platform,
            command=command,
            read_only_expected=read_only_expected,
            mcp_only=mcp_only,
            job_id_pattern=job_id_pattern,
        )

    return environments
