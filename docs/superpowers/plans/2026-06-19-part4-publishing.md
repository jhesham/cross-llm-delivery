# Sub-plan 4 — Publishing (the final sub-plan of spec #2)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). One sitting; commit each task; update STATUS.md before stopping. **Read the MASTER plan's Global Constraints first** (`2026-06-19-per-provider-split-MASTER.md`). Builds on SP1–SP3 (the generator produces self-contained, trimmed, smoke-checked `dist/cross-llm-<provider>/` bundles). **All Claude.**

**Goal:** Publish each generated per-provider skill to its own standalone mirror repo + a `cross-llm-all` umbrella repo, one lockstep VERSION tag — and retire the old unified skill. **Safety-first:** publishing is **dry-run by default**; a real push requires an explicit `--execute` flag AND configured remotes. Tests are NETWORK-FREE (they push to a local bare git repo, never a real host).

**Spec:** `2026-06-19-per-provider-split-design.md` (Part D).

**Order:** T1 → T2 → T3 → T4. All Claude.

**Critical safety constraint (binds every task):** NO network operation runs by default or in any test. `publish.py` defaults to dry-run (prints the plan, touches nothing). `--execute` performs git operations via an INJECTED runner; tests inject a runner that operates on a LOCAL BARE REPO (`git init --bare` in a tmp dir) — proving the mechanics with zero network. The controller will confirm real remotes with the user before any real push; do NOT hardcode or invent real remote URLs.

---

## Task 1: `publish-targets.toml` + loader  [Claude]

**Files:** Create `generator/publish-targets.example.toml`; Modify `generator/build_skill.py` OR create `generator/publish.py` (put the loader where T2's publish.py will live — create `generator/publish.py`); Test `tests/test_publish.py`.

**Interfaces:**
- Produces: `load_publish_targets(path) -> dict` in `generator/publish.py` — parses a TOML mapping `{provider_name: remote_url, "all": umbrella_url}`. Uses stdlib `tomllib` (read-binary). Raises `FileNotFoundError`/`ValueError` clearly on a missing/malformed file.
- `generator/publish-targets.example.toml` — a documented EXAMPLE (placeholder URLs + comments) the user copies to a real (gitignored) `publish-targets.toml` and fills. Do NOT commit a real config.

- [ ] **Step 1: Write the failing test** (`tests/test_publish.py`)
```python
from pathlib import Path
from generator.publish import load_publish_targets
import pytest


def _write(tmp, body):
    p = tmp / "targets.toml"; p.write_text(body, encoding="utf-8"); return p


def test_loads_provider_and_umbrella_targets(tmp_path):
    p = _write(tmp_path,
        'gemini = "git@example.com:me/cross-llm-gemini.git"\n'
        'cursor = "git@example.com:me/cross-llm-cursor.git"\n'
        'all = "git@example.com:me/cross-llm-all.git"\n')
    t = load_publish_targets(p)
    assert t["gemini"].endswith("cross-llm-gemini.git")
    assert t["all"].endswith("cross-llm-all.git")


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_publish_targets(tmp_path / "nope.toml")


def test_example_config_exists_and_is_documented():
    ex = Path("generator/publish-targets.example.toml").read_text(encoding="utf-8")
    assert "all" in ex and "#" in ex   # has the umbrella key + explanatory comments
```

- [ ] **Step 2: Run red** — `python -m pytest tests/test_publish.py -q -p no:warnings` (no module).
- [ ] **Step 3: Implement** — `generator/publish.py` with `load_publish_targets(path)` (`import tomllib`; `path=Path(path)`; if not exists → `FileNotFoundError`; `tomllib.load(open(path,"rb"))`; return the dict). Create `generator/publish-targets.example.toml` with commented placeholder lines for each provider + `all`. Add `publish-targets.toml` (the REAL one) to the repo `.gitignore`.
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add generator/publish.py generator/publish-targets.example.toml tests/test_publish.py .gitignore
git commit -m "feat(publish): publish-targets loader + example config (real config gitignored)"
```

---

## Task 2: `publish_one` — dry-run default + execute via injected runner  [Claude]

**Files:** Modify `generator/publish.py`; Test `tests/test_publish.py` (append).

**Interfaces:**
- Produces:
  - `publish_one(provider, *, targets, version, dist_root="dist", execute=False, runner=None) -> dict` — regenerates the bundle (`build_one(provider, out_root=dist_root)`), strips `__pycache__`/`*.pyc` from it (the SP3 carry), and returns a **plan dict** `{"provider","repo","version","files":N,"actions":[...]}`. When `execute=False` (default): performs NO git/network — just returns the plan (and the caller may print it). When `execute=True`: runs the git sequence via `runner(args, cwd)` against `targets[provider]` (clean working clone → copy bundle as repo root → `git add -A` → commit `f"release v{version} (generated from {sha})"` → `git tag v{version}` → `git push`/`--tags`). `runner` defaults to a real git runner (utf-8/replace).
  - `main(argv)` for `publish.py`: `--all` | `<provider>`, `--targets <toml>` (default `generator/publish-targets.toml`), `--version` (default from repo `VERSION`), `--execute` (default off → dry-run), `--dist-root`. Prints each plan; only pushes when `--execute`.
- The git sequence must be idempotent for a mirror (a generated mirror is overwritten each release — use a clean commit on the default branch; force is acceptable for a generated mirror, but prefer a clean replace+commit).

- [ ] **Step 1: Write the failing tests** (append) — dry-run (no network) + execute against a LOCAL BARE REPO (real git, zero network):
```python
import subprocess, sys, os
from generator.publish import publish_one


def _git(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (p.returncode, (p.stdout or "") + (p.stderr or ""))


def test_dry_run_touches_nothing_and_returns_plan(tmp_path):
    targets = {"cursor": "git@example.com:me/cross-llm-cursor.git"}
    plan = publish_one("cursor", targets=targets, version="9.9.9",
                       dist_root=tmp_path, execute=False)
    assert plan["provider"] == "cursor"
    assert plan["repo"].endswith("cross-llm-cursor.git")
    assert plan["version"] == "9.9.9"
    assert plan["files"] > 0
    # dry-run must NOT have pushed anything (no network); the plan lists intended actions
    assert any("push" in a.lower() for a in plan["actions"])


def test_execute_pushes_to_local_bare_repo(tmp_path):
    # a LOCAL bare repo stands in for the remote -> real git, zero network
    remote = tmp_path / "remote.git"
    _git(["git", "init", "--bare", str(remote)], str(tmp_path))
    targets = {"cursor": str(remote)}
    publish_one("cursor", targets=targets, version="9.9.9",
                dist_root=tmp_path / "dist", execute=True, runner=_git)
    # clone the bare repo and verify the skill landed at the repo ROOT + the tag exists
    work = tmp_path / "verify"
    _git(["git", "clone", str(remote), str(work)], str(tmp_path))
    assert (work / "SKILL.md").is_file()                 # repo root IS the skill
    assert (work / "scripts" / "cld_providers" / "cursor").is_dir()
    rc, tags = _git(["git", "tag"], str(work))
    assert "v9.9.9" in tags
    # trimmed: no __pycache__ committed
    rc, ls = _git(["git", "ls-files"], str(work))
    assert "__pycache__" not in ls and ".pyc" not in ls
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** `publish_one` + `main` in `generator/publish.py`. Reuse `build_one` (from `build_skill.py`) to regenerate the bundle; a `_strip_pycache(path)` helper (walk + remove `__pycache__` dirs and `*.pyc`). For execute: do the git work in a temp dir via `runner` (init/clone the remote, replace contents with the bundle, add/commit/tag/push). Compute the sha via `build_skill._git_sha()`. The bundle's own `.gitignore` excludes pycache, but strip it anyway before commit (belt-and-suspenders for the SP3 carry). Use `--no-smoke`? No — keep smoke on (build_one default) so a broken bundle never gets published. stdlib only.
- [ ] **Step 4: Green + full suite** (the local-bare-repo test proves real push mechanics, network-free).
- [ ] **Step 5: Commit**
```bash
git add generator/publish.py tests/test_publish.py
git commit -m "feat(publish): publish_one (dry-run default; --execute pushes via injected runner); pycache strip"
```

---

## Task 3: `publish_umbrella` — the `cross-llm-all` repo  [Claude]

**Files:** Modify `generator/publish.py`; Test `tests/test_publish.py` (append).

**Interfaces:**
- Produces: `publish_umbrella(*, targets, version, dist_root="dist", execute=False, runner=None) -> dict` — assembles ALL providers' generated bundles side by side into an umbrella layout (`<umbrella>/cross-llm-<provider>/...` for each) + a top `README.md` ("copy the folder(s) you want; each is a self-contained skill") + banner/version; dry-run default; execute pushes to `targets["all"]` via the runner (same git sequence + `v{version}` tag). `main` gains `--umbrella` (and `--all` may also publish the umbrella after the per-provider repos).

- [ ] **Step 1: Write the failing tests** (append)
```python
from generator.publish import publish_umbrella


def test_umbrella_dry_run_lists_all_providers(tmp_path):
    targets = {"all": "git@example.com:me/cross-llm-all.git"}
    plan = publish_umbrella(targets=targets, version="9.9.9",
                            dist_root=tmp_path / "dist", execute=False)
    # the umbrella bundles every known provider
    from generator.build_skill import _known_providers
    for p in _known_providers():
        assert f"cross-llm-{p}" in plan["bundled"]


def test_umbrella_execute_to_local_bare_repo(tmp_path):
    remote = tmp_path / "all.git"
    _git(["git", "init", "--bare", str(remote)], str(tmp_path))
    publish_umbrella(targets={"all": str(remote)}, version="9.9.9",
                     dist_root=tmp_path / "dist", execute=True, runner=_git)
    work = tmp_path / "verify-all"
    _git(["git", "clone", str(remote), str(work)], str(tmp_path))
    from generator.build_skill import _known_providers
    for p in _known_providers():
        assert (work / f"cross-llm-{p}" / "SKILL.md").is_file()
    assert (work / "README.md").is_file()
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** `publish_umbrella` (regenerate each provider via `build_one` into a temp umbrella dir as `cross-llm-<provider>/`, strip pycache, write the top README + banner, dry-run/execute via runner). Wire into `main` (`--umbrella`; `--all --execute` also publishes the umbrella).
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add generator/publish.py tests/test_publish.py
git commit -m "feat(publish): cross-llm-all umbrella (dry-run default; --execute to local-bare-repo proven)"
```

---

## Task 4: Retire the old unified skill + monorepo README  [Claude]

**Files:** Modify `README.md`; Modify `skill/SKILL.md` (deprecate) or remove it; Modify `STATUS.md`; (the global `~/.claude/skills/cross-llm-delivery/` unified skill is retired — note it, don't delete user files from the plan).

**Interfaces:** docs only — point users at the per-provider install; mark the unified skill superseded.

- [ ] **Step 1: Write the check** (append to `tests/test_publish.py`)
```python
def test_readme_documents_per_provider_install():
    r = Path("README.md").read_text(encoding="utf-8")
    assert "cross-llm-" in r                       # references the per-provider skills
    assert "generator/build_skill.py" in r or "build_skill" in r   # how to generate
```

- [ ] **Step 2: Run red** (if README doesn't yet cover it).
- [ ] **Step 3: Implement**
  - `README.md`: add a "Per-provider skills" section — explain the monorepo is the source; `python generator/build_skill.py <provider>` (or `--all`) generates `dist/cross-llm-<provider>/`; users install ONE provider by copying that folder into `~/.claude/skills/`, or grab a published mirror repo / the `cross-llm-all` umbrella; publishing via `generator/publish.py` (dry-run default, `--execute` with `publish-targets.toml`). Mark the old single unified skill as **superseded** by the per-provider skills.
  - `skill/SKILL.md` (the OLD unified multi-provider doc): it has been SUPERSEDED by `skill/SKILL.template.md` + the per-provider fragments. Either delete it OR replace its body with a one-line deprecation pointer to the per-provider skills + the template. (Keep `skill/SKILL.template.md`, `skill/scripts/run_delivery.py`, `skill/references/*` — those are live generator inputs.) Confirm nothing in `src`/`tests`/`generator` imports/reads `skill/SKILL.md` (grep first); if a test references it, update it.
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit + advance STATUS**
```bash
git add README.md skill/SKILL.md STATUS.md tests/test_publish.py
git commit -m "docs(publish): per-provider install in README; retire the unified skill (superseded)"
```
Update STATUS.md: SP4 done → **spec #2 COMPLETE** (per-provider split shipped). Next = the post-rebuild queue (Antigravity provider + cursor direct-node fix).

---

## Done criteria (Sub-plan 4)
- `generator/publish.py`: `load_publish_targets` + `publish_one` + `publish_umbrella` + `main`. **Dry-run by default** (no network); `--execute` pushes via an injected git runner. Proven network-free against a local bare repo: the skill lands at the mirror repo ROOT, tagged `v{VERSION}`, with no `__pycache__` committed; the umbrella bundles every provider.
- `publish-targets.example.toml` documents the config; the real `publish-targets.toml` is gitignored.
- README documents per-provider generation + install + publishing; the old unified skill is retired/superseded.
- Full suite green. STATUS: spec #2 COMPLETE; next = post-rebuild queue.
- **No real push performed by the build** — that's a deliberate, user-confirmed manual `--execute` step later.
