"""Resolve the native Codex executable without invoking a platform shell."""
from __future__ import annotations

import platform
import shutil

from cld.native_cli import NativeCliError as CodexLauncherError  # noqa: F401
from cld.native_cli import NativeCommand as CodexCommand
from cld.native_cli import resolve_native


def _arch(machine):
    if str(machine).upper() in ("ARM64", "AARCH64"):
        return "arm64", "aarch64-pc-windows-msvc"
    return "x64", "x86_64-pc-windows-msvc"


def resolve_codex_command(env=None, which=shutil.which, os_name=None, machine=None) -> CodexCommand:
    """CODEX_CLI_CMD, codex(.exe) on PATH, or the native binary behind an npm shim.

    npm installs expose a ``codex.cmd`` shim; the native executable lives in the
    platform package's vendor directory (nested, hoisted, or legacy layout).
    """
    arch, triple = _arch(platform.machine() if machine is None else machine)

    def candidates(shim_dir):
        package_root = shim_dir / "node_modules" / "@openai" / "codex"
        return (
            package_root / "node_modules" / "@openai" / f"codex-win32-{arch}" / "vendor" / triple / "bin" / "codex.exe",
            shim_dir / "node_modules" / "@openai" / f"codex-win32-{arch}" / "vendor" / triple / "bin" / "codex.exe",
            package_root / "vendor" / triple / "bin" / "codex.exe",
        )

    def npm_env(shim_dir):
        return {"CODEX_MANAGED_BY_NPM": "1",
                "CODEX_MANAGED_PACKAGE_ROOT": str(shim_dir / "node_modules" / "@openai" / "codex")}

    return resolve_native(logical="codex", override_var="CODEX_CLI_CMD", npm_candidates=candidates,
                          npm_env=npm_env, env=env, which=which, os_name=os_name)
