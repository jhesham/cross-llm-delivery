"""Package the generated dist/ skills as committed Claude Code plugins under plugins/.

Layout produced (per provider):
    plugins/cross-llm-<p>/.claude-plugin/plugin.json
    plugins/cross-llm-<p>/skills/cross-llm-<p>/<the generated skill>

Together with .claude-plugin/marketplace.json at the repo root, the repo doubles as a
self-hosted plugin marketplace:
    /plugin marketplace add jhesham/cross-llm-delivery
    /plugin install cross-llm-<p>@cross-llm-delivery

Idempotence: the dist SKILL.md banner embeds the git SHA, which would churn a commit on
every regeneration; in the plugin copy the banner is normalized to a version-only form so
re-running this script produces byte-identical output unless real content changed.
(Plugin updates are versioned by git commits — provenance lives in git history.)

Run AFTER `python generator/build_skill.py --all`:
    python generator/build_plugins.py
"""
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


def main() -> int:
    changed = []
    for p in PROVIDERS:
        dist = ROOT / "dist" / f"cross-llm-{p}"
        if not dist.is_dir():
            print(f"ERROR: {dist} missing - run `python generator/build_skill.py --all` first.")
            return 1
        plug = ROOT / "plugins" / f"cross-llm-{p}"
        # snapshot old state for change detection
        before = {str(f.relative_to(plug)): f.read_bytes()
                  for f in plug.rglob("*") if f.is_file()} if plug.exists() else None
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
        after = {str(f.relative_to(plug)): f.read_bytes()
                 for f in plug.rglob("*") if f.is_file()}
        if before != after:
            changed.append(p)
    print(f"plugins/ refreshed. changed: {', '.join(changed) if changed else 'none (idempotent)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
