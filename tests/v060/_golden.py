"""Snapshot of the v0.6.1 Claude Code and Codex bundles, which v0.7.0 may change only as allowed.

v0.7.0 allowances are optional (the check passes before and after GENMCP): files in
ALLOWED_CHANGES may be added or changed but need not be, and NEW_ENGINE_FILES are
subtracted from both the generated and the golden engine sets.

Generator-owned files are compared by content against golden/claude_codex_bundles.json,
normalising only the generated banner and line endings (the generator writes platform
newlines). Vendored engine files under scripts/cld and scripts/cld_providers are compared
byte-for-byte against the current engine source, because v0.6.0 changes the engine.

Regenerate (only from the v0.6.1 generator):
    python tests/v060/_golden.py      # from the repo root
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = Path(__file__).with_name("golden") / "claude_codex_bundles.json"
PROVIDERS = ("antigravity", "claude", "codex", "cursor", "opencode")
BUNDLES = tuple(f"{host}/{p}" for host in ("claude-code", "codex") for p in PROVIDERS) + (
    "claude-code/unified",)
BANNER = re.compile(r"<!-- GENERATED from cross-llm-delivery[^\n]*-->")
ENGINE_DIRS = ("scripts/cld/", "scripts/cld_providers/")
# v0.7.0 adds these engine modules, and every bundle vendors the whole core.
NEW_ENGINE_FILES = {"scripts/cld/mcp_server.py", "scripts/cld/mcp_jobs.py"}
# v0.7.0 GENMCP may add the entry script and change the skill text.
ALLOWED_CHANGES = {"scripts/cld_mcp.py", "SKILL.md", "references/codex-workflow.md",
                   "references/antigravity-workflow.md"}


def _digest(path):
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return hashlib.sha256(data).hexdigest()
    text = BANNER.sub("{{BANNER}}", text.replace("\r\n", "\n"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def inventory(bundle):
    files, engine = {}, []
    for path in sorted(p for p in Path(bundle).rglob("*") if p.is_file()):
        rel = path.relative_to(bundle).as_posix()
        if "__pycache__" in rel.split("/"):
            continue
        if rel.startswith(ENGINE_DIRS):
            engine.append(rel)
        else:
            files[rel] = _digest(path)
    return {"files": files, "engine": engine}


def assert_unchanged(key, bundle):
    """Fail with the differing paths when a Claude Code or Codex bundle drifts from v0.6.1."""
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))[key]
    got = inventory(bundle)
    extra = sorted(set(got["files"]) - set(want["files"]) - ALLOWED_CHANGES)
    missing = sorted(set(want["files"]) - set(got["files"]))
    assert not extra and not missing, (key, "added:", extra, "removed:", missing)
    changed = sorted(rel for rel, digest in want["files"].items()
                     if rel not in ALLOWED_CHANGES and got["files"][rel] != digest)
    assert not changed, (key, "content changed:", changed)
    engine = set(got["engine"]) - NEW_ENGINE_FILES
    assert engine == set(want["engine"]) - NEW_ENGINE_FILES, (
        key, "vendored engine files added:", sorted(engine - set(want["engine"])),
        "removed:", sorted(set(want["engine"]) - engine))
    stale = sorted(rel for rel in got["engine"]
                   if (Path(bundle) / rel).read_bytes()
                   != (ROOT / "engine" / rel.split("/", 1)[1]).read_bytes())
    assert not stale, (key, "vendored engine files differ from engine/:", stale)


def _build_all(out_root):
    from generator.build_skill import build_one, build_unified
    bundles = {}
    for key in BUNDLES:
        host, provider = key.split("/")
        if provider == "unified":
            out = build_unified(out_root=out_root, smoke=False)
        else:
            out = build_one(provider, out_root=out_root, smoke=False, host=host)
        bundles[key] = inventory(Path(out))
    return bundles


if __name__ == "__main__":
    import sys
    import tempfile
    sys.path[:0] = [str(ROOT), str(ROOT / "engine")]
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = _build_all(Path(tmp))
    GOLDEN.parent.mkdir(exist_ok=True)
    GOLDEN.write_text(json.dumps(snapshot, indent=1, sort_keys=True) + "\n",
                      encoding="utf-8", newline="\n")
    print(f"wrote {GOLDEN.relative_to(ROOT)}: {len(snapshot)} bundles")
