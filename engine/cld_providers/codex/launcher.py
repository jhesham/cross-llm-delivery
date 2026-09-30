"""Resolve the native Codex executable without invoking a platform shell."""
from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path


class CodexLauncherError(RuntimeError):
    """The Codex CLI cannot be launched safely from this environment."""


@dataclass(frozen=True)
class CodexCommand:
    path: str
    env: dict[str, str]


def _existing_file(path):
    try:
        return Path(path).is_file()
    except (OSError, TypeError, ValueError):
        return False


def resolve_codex_command(env=None, which=shutil.which, os_name=None, machine=None) -> CodexCommand:
    """Find a directly executable Codex binary, never a Windows command shim.

    On Windows, npm installs expose a ``codex.cmd`` shim. We resolve the native
    executable in the package's vendor directory instead of passing that shim
    to a process launcher that deliberately does not use a shell.
    """
    env = os.environ if env is None else env
    os_name = os.name if os_name is None else os_name
    machine = platform.machine() if machine is None else machine

    if "CODEX_CLI_CMD" in env:
        override = env["CODEX_CLI_CMD"]
        try:
            valid = isinstance(override, str) and Path(override).is_absolute() and Path(override).is_file()
        except (OSError, TypeError, ValueError):
            valid = False
        if not valid:
            raise CodexLauncherError(
                "CODEX_CLI_CMD must name an absolute path to an existing file"
            )
        return CodexCommand(str(Path(override).resolve()), {})

    if os_name != "nt":
        candidate = which("codex")
        if candidate and _existing_file(candidate):
            return CodexCommand(str(candidate), {})
        raise CodexLauncherError("Codex CLI not found; install it or set CODEX_CLI_CMD to an absolute executable path")

    candidate = which("codex.exe")
    if candidate and _existing_file(candidate):
        return CodexCommand(str(candidate), {})

    shim = which("codex.cmd")
    if shim:
        shim_dir = Path(shim).parent
        if str(machine).upper() in ("ARM64", "AARCH64"):
            arch, triple = "arm64", "aarch64-pc-windows-msvc"
        else:
            arch, triple = "x64", "x86_64-pc-windows-msvc"

        package_root = shim_dir / "node_modules" / "@openai" / "codex"
        candidates = (
            package_root / "node_modules" / "@openai" / f"codex-win32-{arch}" / "vendor" / triple / "bin" / "codex.exe",
            shim_dir / "node_modules" / "@openai" / f"codex-win32-{arch}" / "vendor" / triple / "bin" / "codex.exe",
            package_root / "vendor" / triple / "bin" / "codex.exe",
        )
        for native in candidates:
            if _existing_file(native):
                return CodexCommand(str(native), {
                    "CODEX_MANAGED_BY_NPM": "1",
                    "CODEX_MANAGED_PACKAGE_ROOT": str(package_root),
                })
        raise CodexLauncherError(
            f"Only the npm Codex shim was found at {shim}; set CODEX_CLI_CMD to an absolute path to the native executable"
        )

    raise CodexLauncherError("Codex CLI not found; install it or set CODEX_CLI_CMD to an absolute executable path")
