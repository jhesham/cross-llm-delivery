"""Codex configuration inputs that can change model routing or execution policy."""
from __future__ import annotations

import os
from pathlib import Path
import tomllib


def _absolute_codex_home() -> Path:
    """Resolve the selected Codex home, rejecting cwd-dependent relative homes."""
    raw_home = os.environ.get("CODEX_HOME")
    if raw_home is None:
        return (Path.home() / ".codex").resolve()
    home = Path(raw_home).expanduser()
    if not home.is_absolute():
        raise ValueError("CODEX_HOME must be an absolute path for stable Codex validation")
    return home.resolve()


def _project_inputs(repository: Path) -> list[Path]:
    """Include every possible project layer through the filesystem root."""
    inputs = []
    current = repository.resolve()
    while True:
        inputs.append(current / ".codex" / "config.toml")
        if current.parent == current:
            return inputs
        current = current.parent


def config_inputs(repository: str | os.PathLike[str]) -> tuple[Path, ...]:
    """Return Codex's selected home, project, and platform-managed config files.

    Missing candidates remain inputs so later creation also changes admission
    identity. Profile, authentication, and session files are not selected by
    CLD's fixed invocation and deliberately are not included here.
    """
    selected_home = _absolute_codex_home()
    paths = [selected_home / "config.toml", *_project_inputs(Path(repository))]

    if os.name == "nt":
        paths.append(selected_home / "managed_config.toml")
        default_home = (Path.home() / ".codex").resolve()
        if os.path.normcase(str(default_home)) != os.path.normcase(str(selected_home)):
            paths.append(default_home / "managed_config.toml")
        program_data = next((value for name, value in os.environ.items()
                             if name.casefold() == "programdata"), None)
        if program_data:
            system_config = Path(program_data) / "OpenAI" / "Codex"
            paths.extend(
                system_config / name for name in ("config.toml", "requirements.toml")
            )
    else:
        system_codex = Path("/etc/codex")
        paths.extend(system_codex / name for name in
                     ("config.toml", "requirements.toml", "managed_config.toml"))

    # Preserve order while collapsing aliases and repeated candidates.
    unique, seen = [], set()
    for path in paths:
        path = Path(path).resolve()
        key = os.path.normcase(os.path.normpath(str(path)))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return tuple(unique)


def config_env(paths) -> tuple[str, ...]:
    """Return names of environment-backed Codex provider credentials.

    Environment values are never returned here; the shared validation context
    hashes those values and records only their variable names.
    """
    names = set()
    for raw_path in paths:
        path = Path(raw_path)
        if path.suffix.casefold() != ".toml":
            continue
        try:
            with path.open("rb") as stream:
                config = tomllib.load(stream)
        except FileNotFoundError:
            continue
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
            # Do not surface parser diagnostics: they may include configuration
            # values. Invalid or unreadable TOML must fail closed before validation.
            raise ValueError("Unable to read or parse Codex TOML configuration") from None

        providers = config.get("model_providers", {})
        if not isinstance(providers, dict):
            continue
        for provider in providers.values():
            if not isinstance(provider, dict):
                continue
            env_key = provider.get("env_key")
            if isinstance(env_key, str) and env_key:
                names.add(env_key)
            headers = provider.get("env_http_headers", {})
            if isinstance(headers, dict):
                names.update(value for value in headers.values()
                             if isinstance(value, str) and value)

    return tuple(sorted(names))
