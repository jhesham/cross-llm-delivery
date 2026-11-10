#!/usr/bin/env python3
"""Safely preview, install, or uninstall Antigravity skill bundles.

All destinations are relative to an explicit scope root. Ownership validation,
staging, publication and rollback are shared with the Codex installer.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__:
    from . import install_codex as shared
else:  # Direct invocation: python generator/install_antigravity.py
    import install_codex as shared


SUPPORTED_NAMES = frozenset({
    "cross-llm-opencode-agy",
    "cross-llm-antigravity-agy",
    "cross-llm-cursor-agy",
    "cross-llm-codex-agy",
    "cross-llm-claude-agy",
    "cross-llm-delivery-agy",
})
INSTALLER_MARKER = "cross-llm-delivery/install_antigravity.py"


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely manage Antigravity bundles under an explicit scope root.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--preview", action="store_true",
                         help="Report the destination and outcome without writing.")
    actions.add_argument("--install", action="store_true",
                         help="Install or update a clean owned bundle.")
    actions.add_argument("--uninstall", action="store_true",
                         help="Remove a clean owned bundle.")
    parser.add_argument("--scope", required=True, choices=("workspace", "user"))
    parser.add_argument("--scope-root", required=True, metavar="PATH")
    parser.add_argument("--bundle", metavar="PATH")
    parser.add_argument("--name", metavar="NAME")
    shared._add_mcp_arguments(parser)
    return parser.parse_args(argv)


def _workspace_warnings(root: Path, name: str) -> dict[str, str]:
    warnings = {}
    sibling = root / ".agents" / "skills" / name.removesuffix("-agy")
    if sibling.exists():
        warnings["sibling_warning"] = (
            f"Antigravity also sees the Codex copy at {sibling}; "
            f"ask Antigravity for {name} by name.")
    shadow = root / ".agent" / "skills" / name
    if shadow.exists():
        warnings["shadow_warning"] = (
            f"A copy exists at {shadow}; Antigravity also reads the deprecated "
            ".agent folder.")
    return warnings


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    action = shared._action(args)
    target_str = None
    warnings: dict[str, str] = {}
    ownership = {"marker": INSTALLER_MARKER, "collision_on_modified": True}
    try:
        shared._check_actions(args)
        root = Path(args.scope_root).absolute()
        skills = (root / ".agents" / "skills" if args.scope == "workspace"
                  else root / ".gemini" / "config" / "skills")
        config = root / ".gemini" / "config" / "mcp_config.json"
        if args.register_mcp or args.unregister_mcp:
            target_str = str(config)
            if args.scope != "user":
                raise shared.Reject("Antigravity MCP registration requires --scope user")
            payload = shared._mcp_action(
                args, root, skills / "cross-llm-delivery-agy", config,
                host="antigravity", marker=INSTALLER_MARKER)
        elif action == "uninstall":
            if not args.name:
                raise shared.Reject("--uninstall requires --name cross-llm-<provider>-agy")
            name = shared._validate_name(args.name, SUPPORTED_NAMES)
            target = skills / name
            target_str = str(target)
            payload = shared._locked_uninstall(
                root, target, name, config, host="antigravity", **ownership)
        else:
            source, name = shared._validate_bundle(
                args.bundle, SUPPORTED_NAMES,
                required_files=(Path("references") / "antigravity-workflow.md",))
            target = skills / name
            target_str = str(target)
            if args.scope == "workspace":
                warnings = _workspace_warnings(root, name)
            shared._check_separation(source, target)
            if action == "preview":
                payload = shared._preview(root, target, **ownership)
            else:
                payload = shared._install(
                    source, root, target, name, host="Antigravity", **ownership)
    except (shared.Reject, shared.OwnerBusy, OSError) as exc:
        payload = {
            "action": action,
            "target": target_str,
            "outcome": "error",
            "error": (str(exc) if isinstance(exc, shared.Reject)
                      else f"{type(exc).__name__}: {exc}"),
        }
        if isinstance(exc, shared.Reject) and exc.collision:
            payload["collision"] = "unowned"
    payload.update(warnings)
    payload["scope"] = args.scope
    print(json.dumps(payload, sort_keys=True))
    return 1 if payload["outcome"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
