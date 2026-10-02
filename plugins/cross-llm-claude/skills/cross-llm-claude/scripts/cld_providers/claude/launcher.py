"""Resolve the native Claude Code executable without a shell."""
from __future__ import annotations

import shutil

from cld.native_cli import NativeCliError as ClaudeLauncherError  # noqa: F401
from cld.native_cli import NativeCommand, resolve_native


def resolve_claude_command(env=None, which=shutil.which, os_name=None) -> NativeCommand:
    # The npm claude.cmd shim itself invokes node_modules/@anthropic-ai/claude-code/bin/claude.exe.
    return resolve_native(
        logical="claude", override_var="CLAUDE_CLI_CMD",
        npm_candidates=lambda shim_dir: (
            shim_dir / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe",),
        env=env, which=which, os_name=os_name)
