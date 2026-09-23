"""Package the generated dist/ skills as committed Claude Code plugins under plugins/.

Layout produced (per provider):
    plugins/cross-llm-<p>/.claude-plugin/plugin.json
    plugins/cross-llm-<p>/skills/cross-llm-<p>/<the generated skill>

Together with .claude-plugin/marketplace.json at the repo root, the repo doubles as a
self-hosted plugin marketplace:
    /plugin marketplace add jhesham/cross-llm-delivery
    /plugin install cross-llm-<p>@cross-llm-delivery

Codex host mode (--host codex) packages the generated Codex bundles instead:
    <out-root>/codex/cross-llm-<p>/plugin.json            (portable manifest at root)
    <out-root>/codex/cross-llm-<p>/skills/cross-llm-<p>/<the generated codex skill>
Codex mode reads <dist-root>/codex/cross-llm-<p> (build with
`python generator/build_skill.py --all --host codex` first) and never touches an
adjacent Claude plugin tree. Its manifest carries the official schema URL, the
existing plugin name, the VERSION semantic version, description and author; it
claims no submission or readiness that has not been validated.

Idempotence: the dist SKILL.md banner embeds the git SHA, which would churn a commit on
every regeneration; in the plugin copy the banner is normalized to a version-only form so
re-running this script produces byte-identical output unless real content changed.
(Plugin updates are versioned by git commits — provenance lives in git history.)

Run AFTER `python generator/build_skill.py --all`:
    python generator/build_plugins.py
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("antigravity", "opencode", "cursor")
DESCRIPTIONS = {
    "antigravity": "Delegate bulk implementation to Google's Antigravity CLI (flat-rate Gemini/Claude models) with Claude as architect + judge; committed failing tests gate every merge.",
    "opencode": "Delegate bulk implementation to OpenCode CLI models (free/cheap-metered: deepseek, kimi, GLM, ...) with Claude as architect + judge; committed failing tests gate every merge.",
    "cursor": "Delegate bulk implementation to Cursor's cursor-agent (composer-2.5) with Claude as architect + judge; committed failing tests gate every merge.",
}
CODEX_DESCRIPTIONS = {
    "antigravity": "Delegate bulk implementation to Google's Antigravity CLI (flat-rate Gemini/Claude models) with Codex as architect + judge; committed failing tests gate every merge.",
    "opencode": "Delegate bulk implementation to OpenCode CLI models (free/cheap-metered: deepseek, kimi, GLM, ...) with Codex as architect + judge; committed failing tests gate every merge.",
    "cursor": "Delegate bulk implementation to Cursor's cursor-agent (composer-2.5) with Codex as architect + judge; committed failing tests gate every merge.",
}
CODEX_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
_BANNER_SHA = re.compile(r"(GENERATED from cross-llm-delivery)@[0-9a-f]+")
_SKIP = ("__pycache__", ".pyc", ".pytest_cache")


def _normalize_banner(text: str) -> str:
    return _BANNER_SHA.sub(r"\1", text)


def _copy_skill(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    for f in src.rglob("*"):
        if f.is_dir() or any(s in str(f) for s in _SKIP):
            continue
        rel = f.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix in (".md", ".py", ".txt", ".json", ".toml"):
            out.write_text(_normalize_banner(f.read_text(encoding="utf-8")),
                           encoding="utf-8", newline="\n")
        else:
            shutil.copy2(f, out)


def _snapshot(root: Path) -> dict[str, bytes] | None:
    if not root.exists():
        return None
    return {str(f.relative_to(root)): f.read_bytes()
            for f in root.rglob("*") if f.is_file()}


def _version() -> str:
    """Read the VERSION file beside this generator's repo root."""
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _main_claude(dist_root: Path, out_root: Path) -> int:
    """Default host: refresh committed Claude plugins (layout/names unchanged)."""
    changed = []
    for p in PROVIDERS:
        dist = dist_root / f"cross-llm-{p}"
        if not dist.is_dir():
            print(f"ERROR: {dist} missing - run `python generator/build_skill.py --all` first.")
            return 1
        plug = out_root / f"cross-llm-{p}"
        # snapshot old state for change detection
        before = _snapshot(plug)
        (plug / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        manifest = {
            "name": f"cross-llm-{p}",
            "description": DESCRIPTIONS[p],
            "author": {"name": "cross-llm-delivery contributors"},
            # no "version": every git commit is a new version (active development)
        }
        (plug / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        _copy_skill(dist, plug / "skills" / f"cross-llm-{p}")
        after = _snapshot(plug)
        if before != after:
            changed.append(p)
    print(f"plugins/ refreshed. changed: {', '.join(changed) if changed else 'none (idempotent)'}")
    return 0


def _main_codex(dist_root: Path, out_root: Path) -> int:
    """Codex host: portable plugins under <out-root>/codex/ from codex bundles.

    Touches only <out-root>/codex/; an adjacent Claude plugin tree is preserved.
    """
    changed = []
    version = _version()
    for p in PROVIDERS:
        dist = dist_root / "codex" / f"cross-llm-{p}"
        if not dist.is_dir():
            print(f"ERROR: {dist} missing - run `python generator/build_skill.py --all --host codex` first.")
            return 1
        plug = out_root / "codex" / f"cross-llm-{p}"
        # snapshot old state for change detection
        before = _snapshot(plug)
        plug.mkdir(parents=True, exist_ok=True)
        manifest = {
            "$schema": CODEX_SCHEMA_URL,
            "name": f"cross-llm-{p}",
            "version": version,
            "description": CODEX_DESCRIPTIONS[p],
            "author": {"name": "cross-llm-delivery contributors"},
        }
        (plug / "plugin.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        _copy_skill(dist, plug / "skills" / f"cross-llm-{p}")
        after = _snapshot(plug)
        if before != after:
            changed.append(p)
    print(f"codex plugins refreshed. changed: {', '.join(changed) if changed else 'none (idempotent)'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Package generated dist/ skills as host plugins.")
    parser.add_argument(
        "--host",
        default="claude-code",
        choices=("claude-code", "codex"),
        help="Target host plugin layout: claude-code (default) or codex.",
    )
    parser.add_argument(
        "--dist-root",
        default=None,
        help="Root of generated bundles (default: <repo>/dist).",
    )
    parser.add_argument(
        "--out-root",
        default=None,
        help="Output root (default: <repo>/plugins for Claude, <repo>/dist/plugins for Codex).",
    )
    args = parser.parse_args(argv)

    dist_root = Path(args.dist_root) if args.dist_root else ROOT / "dist"
    out_root = Path(args.out_root) if args.out_root else ROOT / (
        "dist/plugins" if args.host == "codex" else "plugins")
    if args.host == "codex":
        return _main_codex(dist_root, out_root)
    return _main_claude(dist_root, out_root)


if __name__ == "__main__":
    sys.exit(main())
