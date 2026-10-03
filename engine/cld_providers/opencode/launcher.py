"""Resolve the native OpenCode executable without invoking a platform shell."""
from __future__ import annotations

import shutil

from cld.native_cli import NativeCliError, NativeCommand, resolve_native


def resolve_opencode_command(env=None, which=shutil.which, os_name=None) -> NativeCommand:
    """Resolve OPENCODE_CLI_CMD, a native PATH binary, or npm's installed binary.

    On Windows, npm's ``opencode.cmd`` shim is only used to locate the native
    postinstall target. We do not guess optional platform-package variants.
    """
    return resolve_native(
        logical="opencode",
        override_var="OPENCODE_CLI_CMD",
        npm_candidates=lambda shim_dir: (
            shim_dir / "node_modules" / "opencode-ai" / "bin" / "opencode.exe",
        ),
        env=env,
        which=which,
        os_name=os_name,
    )


__all__ = ["NativeCliError", "NativeCommand", "resolve_opencode_command"]
