# Sub-plan 2 — The generator + outputs

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). One sitting; commit each task; update STATUS.md before stopping. **Read the MASTER plan's Global Constraints + Shared interfaces first** (`2026-06-19-per-provider-split-MASTER.md`). Builds on Sub-plan 1 (the engine is provider-blind; `engine/cld` + `engine/cld_providers/<name>/`; each provider has `provider.py` + `SKILL.fragment.md` + `setup.md`; trimmed-skill readiness proven).

**Goal:** Build `generator/build_skill.py` that composes `engine/cld` + ONE `engine/cld_providers/<x>` into a self-contained, trimmed-vendored skill folder `dist/cross-llm-<x>/` (core + that provider only, no pip install), with a standalone smoke-check that proves the bundle works in isolation.

**Spec:** `2026-06-19-per-provider-split-design.md` (Part C).

**Architecture:** `generator/build_skill.py` exposes `build_one(provider, *, out_root) -> Path` (+ `--all`). It wipes+recreates the output, vendors the core + one provider (trimmed) + the driver (with a `sys.path` shim) + references/examples, composes `SKILL.md` from a core template + the provider's fragment, writes per-repo scaffolding + a GENERATED banner + VERSION stamp, then runs a standalone smoke-check. Outputs are disposable (fully regenerated each run).

**Order:** T1 → T2 → T3 → T4 → T5.

**Builder routing (per the agreed philosophy — engine stable post-SP1, so dogfood is safe):**
T1 = Claude (skeleton/paths). **T2 = DOGFOOD-Gemini** (vendor/trim file ops, test-pinnable). T3 = Claude (author the core SKILL template — judgment). **T4 = DOGFOOD-Gemini** (compose + scaffold, pure string/file logic, fixture-tested). T5 = Claude (subprocess-isolation smoke-check).

---

## Task 1: Generator skeleton + paths + output wipe/recreate  [Claude]

**Files:** Create `generator/__init__.py` (empty), `generator/build_skill.py`; Test `tests/test_generator.py`.

**Interfaces:**
- Produces: `build_one(provider: str, *, out_root: str | Path = "dist") -> Path` (creates+returns `<out_root>/cross-llm-<provider>/`, wiping any existing dir first); `KNOWN_PROVIDERS_DIR = <repo>/engine/cld_providers`; `main(argv=None) -> int` (argparse: positional `provider` OR `--all`; `--out-root`).
- Path resolution must be repo-root-relative and robust to CWD (compute repo root from `__file__`).

- [ ] **Step 1: Write the failing test** (`tests/test_generator.py`)
```python
from pathlib import Path
from generator.build_skill import build_one


def test_build_one_creates_named_output_dir(tmp_path):
    out = build_one("cursor", out_root=tmp_path)
    assert out == tmp_path / "cross-llm-cursor"
    assert out.is_dir()


def test_build_one_is_idempotent_wipes_stale(tmp_path):
    out = build_one("cursor", out_root=tmp_path)
    stale = out / "STALE.txt"
    stale.write_text("old", encoding="utf-8")
    out2 = build_one("cursor", out_root=tmp_path)   # re-run wipes
    assert out2 == out
    assert not stale.exists()                        # stale content gone


def test_build_one_rejects_unknown_provider(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        build_one("nope", out_root=tmp_path)
```

- [ ] **Step 2: Run red** — `python -m pytest tests/test_generator.py -q -p no:warnings` (ImportError / no module).
- [ ] **Step 3: Implement `generator/build_skill.py`:**
  - Compute `REPO_ROOT = Path(__file__).resolve().parents[1]`; `ENGINE = REPO_ROOT/"engine"`; `PROVIDERS_DIR = ENGINE/"cld_providers"`; `SKILL_SRC = REPO_ROOT/"skill"`.
  - `_known_providers() -> list[str]`: the subdirs of `PROVIDERS_DIR` that contain `provider.py` (i.e. `gemini`,`opencode`,`cursor`,`composer`).
  - `build_one(provider, *, out_root="dist")`: validate `provider in _known_providers()` else `ValueError(f"Unknown provider '{provider}'. Known: {...}")`; `out = Path(out_root)/f"cross-llm-{provider}"`; if it exists, `shutil.rmtree(out)`; `out.mkdir(parents=True)`; return `out`. (Vendoring/compose/scaffold/smoke are added in later tasks — for now just the dir.)
  - `main(argv=None)`: argparse `provider` (nargs="?") + `--all` + `--out-root` (default "dist"); for each target provider call `build_one`; print the path(s); return 0. `if __name__ == "__main__": raise SystemExit(main())`.
- [ ] **Step 4: Green + full suite** — `python -m pytest tests/test_generator.py -q -p no:warnings && python -m pytest -p no:warnings -q`.
- [ ] **Step 5: Commit**
```bash
git add generator/__init__.py generator/build_skill.py tests/test_generator.py
git commit -m "feat(generator): build_skill skeleton — build_one wipes+creates dist/cross-llm-<provider>"
```

---

## Task 2: Vendor + trim (core + one provider + driver + references)  [DOGFOOD-Gemini]

**Files:** Modify `generator/build_skill.py`; Modify `skill/scripts/run_delivery.py` (add the `sys.path` shim — see note); Test `tests/test_generator.py` (append).

**Interfaces:**
- Consumes: `build_one` from T1.
- Produces: after `build_one(provider)`, the output contains `scripts/cld/` (verbatim `engine/cld`), `scripts/cld_providers/__init__.py` + `scripts/cld_providers/<provider>/` (ONLY that provider), `scripts/run_delivery.py` (with a leading `sys.path` shim), and `references/` + `examples/` copied from `skill/`.

**`sys.path` shim note:** the vendored `run_delivery.py` must resolve `import cld`/`import cld_providers` from its OWN dir (no pip install). Add this shim to the TOP of the SOURCE `skill/scripts/run_delivery.py` (above the `from cld...` imports), so the generator copies it verbatim and it's harmless in the monorepo (where `cld` is already importable):
```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

- [ ] **Step 1: Write the failing test** (append) — Claude authors this contract before the dogfood dispatch:
```python
def _build(tmp_path, provider="cursor"):
    return build_one(provider, out_root=tmp_path)


def test_vendors_core_and_only_one_provider(tmp_path):
    out = _build(tmp_path, "cursor")
    assert (out / "scripts" / "cld" / "orchestrator.py").is_file()
    assert (out / "scripts" / "cld" / "providers_api.py").is_file()
    assert (out / "scripts" / "cld_providers" / "__init__.py").is_file()
    assert (out / "scripts" / "cld_providers" / "cursor" / "provider.py").is_file()
    # TRIMMED: other providers must NOT be vendored
    assert not (out / "scripts" / "cld_providers" / "opencode").exists()
    assert not (out / "scripts" / "cld_providers" / "gemini").exists()


def test_vendors_driver_with_syspath_shim(tmp_path):
    out = _build(tmp_path, "cursor")
    drv = (out / "scripts" / "run_delivery.py").read_text(encoding="utf-8")
    assert "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))" in drv


def test_vendors_references(tmp_path):
    out = _build(tmp_path, "cursor")
    assert (out / "references" / "authoring-plans.md").is_file()
```

- [ ] **Step 2: Run red** — the vendoring isn't implemented yet.
- [ ] **Step 3: DOGFOOD (Gemini) — implement the vendor/trim functions in `generator/build_skill.py`:**
  Brief for the executor: extend `build_one` to call, after creating the dir:
  - `_vendor_core(out)`: `shutil.copytree(ENGINE/"cld", out/"scripts"/"cld")` (exclude `__pycache__`).
  - `_vendor_provider(provider, out)`: create `out/"scripts"/"cld_providers"`; copy `PROVIDERS_DIR/"__init__.py"` → there; `shutil.copytree(PROVIDERS_DIR/provider, out/"scripts"/"cld_providers"/provider)` (exclude `__pycache__`). Do NOT copy other providers.
  - `_vendor_driver(out)`: copy `SKILL_SRC/"scripts"/"run_delivery.py"` → `out/"scripts"/"run_delivery.py"` (verbatim; the shim is already in the source).
  - `_vendor_aux(out)`: copy `SKILL_SRC/"references"` → `out/"references"` and `SKILL_SRC/"examples"` → `out/"examples"` (exclude `__pycache__`; skip if a dir is absent).
  - Use `shutil.copytree(..., ignore=shutil.ignore_patterns("__pycache__","*.pyc"))`. stdlib only.
  Also (a pre-step, done by Claude or folded into the dispatch): add the `sys.path` shim to `skill/scripts/run_delivery.py` per the note above.
- [ ] **Step 4: Judge** — `python -m pytest tests/test_generator.py -q -p no:warnings && python -m pytest -p no:warnings -q` (green; the shim addition must not break existing run_delivery tests).
- [ ] **Step 5: Commit**
```bash
git add generator/build_skill.py skill/scripts/run_delivery.py tests/test_generator.py
git commit -m "feat(generator): vendor+trim core + single provider + driver(shim) + references (Gemini-built, Claude-judged)"
```

---

## Task 3: Author the core SKILL template  [Claude]

**Files:** Create `skill/SKILL.template.md`; Test `tests/test_generator.py` (append).

**Interfaces:**
- Produces: `skill/SKILL.template.md` — the provider-AGNOSTIC core SKILL prose with placeholders the generator fills: `{{PROVIDER_NAME}}`, `{{DEFAULT_WORKHORSE}}`, `{{PROVIDER_FRAGMENT}}`, `{{SETUP}}`, `{{BANNER}}`.

- [ ] **Step 1: Write the failing test** (append)
```python
def test_skill_template_exists_with_placeholders():
    from pathlib import Path
    t = Path("skill/SKILL.template.md").read_text(encoding="utf-8")
    for ph in ("{{PROVIDER_NAME}}", "{{DEFAULT_WORKHORSE}}", "{{PROVIDER_FRAGMENT}}",
               "{{SETUP}}", "{{BANNER}}"):
        assert ph in t
    # the core template must NOT hardcode a specific provider in its prose
    low = t.lower()
    assert "opencode" not in low and "composer" not in low
```

- [ ] **Step 2: Run red** — template doesn't exist.
- [ ] **Step 3: Implement** — create `skill/SKILL.template.md` by extracting the **provider-agnostic** core from the current `skill/SKILL.md`: the YAML frontmatter (name `cross-llm-{{PROVIDER_NAME}}`, a templated description), what-this-does, when-to-use, the plan format, the `--step` batch loop + gate codes (0/2/3/4) + the repair loop, the routing control-flow (complexity rubric pointer, one-screen plan, run-modes), and the usage view — **with all provider-specific picker/invocation/setup prose replaced by `{{PROVIDER_FRAGMENT}}` and `{{SETUP}}`**, the default workhorse by `{{DEFAULT_WORKHORSE}}`, and a `{{BANNER}}` line at the very top. Do NOT mention gemini/opencode/cursor/composer by name in the core prose (those live in each provider's fragment). Keep it ASCII/cp1252-safe. (Reference `skill/SKILL.md` for the prose to carry over; reference each provider's existing `SKILL.fragment.md` to confirm the split boundary.)
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add skill/SKILL.template.md tests/test_generator.py
git commit -m "feat(generator): core provider-agnostic SKILL.template.md with placeholders"
```

---

## Task 4: SKILL compose + banner + VERSION + per-repo scaffolding  [DOGFOOD-Gemini]

**Files:** Create `VERSION` (repo root, content `0.1.0`); Modify `generator/build_skill.py`; Test `tests/test_generator.py` (append).

**Interfaces:**
- Consumes: `build_one`, the template (T3), each provider's `SKILL.fragment.md`/`setup.md`, `default_workhorse`.
- Produces: after `build_one(provider)`, `<out>/SKILL.md` = the template with placeholders filled; `<out>/README.md`, `<out>/LICENSE`, `<out>/.gitignore`; the GENERATED banner present in SKILL.md + README.

- [ ] **Step 1: Write the failing test** (append) — Claude authors before dispatch:
```python
def test_composes_skill_md(tmp_path):
    out = build_one("cursor", out_root=tmp_path)
    skill = (out / "SKILL.md").read_text(encoding="utf-8")
    # placeholders are gone; provider specifics are in
    assert "{{" not in skill
    assert "cursor" in skill.lower()
    assert "cursor:composer-2.5" in skill            # the provider's default workhorse
    # provider fragment content is woven in (a phrase from cursor's fragment)
    assert "cursor-agent" in skill.lower()
    # GENERATED banner present
    assert "GENERATED" in skill and "do not edit" in skill.lower()
    skill.encode("cp1252")


def test_scaffolds_repo_files(tmp_path):
    out = build_one("cursor", out_root=tmp_path)
    assert (out / "README.md").is_file()
    assert (out / "LICENSE").is_file()
    assert (out / ".gitignore").is_file()
    assert "GENERATED" in (out / "README.md").read_text(encoding="utf-8")


def test_version_stamped(tmp_path):
    out = build_one("cursor", out_root=tmp_path)
    ver = Path("VERSION").read_text(encoding="utf-8").strip()
    assert ver in (out / "SKILL.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: DOGFOOD (Gemini) — implement compose + scaffold in `generator/build_skill.py`:**
  Brief for the executor:
  - `_git_sha()`: `subprocess.run(["git","rev-parse","--short","HEAD"], cwd=REPO_ROOT, ...)` → the sha (or `"unknown"` on failure). stdlib, utf-8/replace.
  - `_banner(provider)`: `f"<!-- GENERATED from cross-llm-delivery@{_git_sha()} (provider: {provider}, v{_version()}) - do not edit here; edit the monorepo source. -->"`.
  - `_version()`: read `REPO_ROOT/"VERSION"` (strip); default `"0.0.0"` if absent.
  - `_compose_skill(provider, out)`: read `skill/SKILL.template.md`; read `engine/cld_providers/<provider>/SKILL.fragment.md` + `setup.md`; resolve the provider's `default_workhorse` (import `cld_providers.<provider>.provider` and read `PROVIDER.default_workhorse`, OR add `engine` to sys.path and `from cld.providers_api import get_provider; load_providers()`); substitute `{{PROVIDER_NAME}}`→provider, `{{DEFAULT_WORKHORSE}}`→default_workhorse, `{{PROVIDER_FRAGMENT}}`→fragment text, `{{SETUP}}`→setup text, `{{BANNER}}`→`_banner(provider)`; write `<out>/SKILL.md`.
  - `_scaffold(provider, out)`: write `<out>/README.md` (banner + a short "self-contained cross-llm-delivery skill for <provider>; drop into ~/.claude/skills/" + install note), `<out>/LICENSE` (copy `REPO_ROOT/"LICENSE"`), `<out>/.gitignore` (`__pycache__/\n*.pyc\n.cld-ledger.json\n`).
  - Wire both into `build_one` after the vendoring step. stdlib only; cp1252-safe output.
  - Create `VERSION` at repo root containing `0.1.0`.
- [ ] **Step 4: Judge** — `python -m pytest tests/test_generator.py -q -p no:warnings && python -m pytest -p no:warnings -q`.
- [ ] **Step 5: Commit**
```bash
git add VERSION generator/build_skill.py tests/test_generator.py
git commit -m "feat(generator): SKILL compose + banner + VERSION + repo scaffolding (Gemini-built, Claude-judged)"
```

---

## Task 5: Standalone smoke-check  [Claude]

**Files:** Modify `generator/build_skill.py`; Test `tests/test_generator.py` (append).

**Interfaces:**
- Produces: `_smoke_check(out) -> None` (raises `RuntimeError` with captured output on failure); `build_one` runs it as the LAST step (a broken vendor fails the build, not the user). A `--no-smoke` flag skips it (for speed in unit tests of earlier steps).

- [ ] **Step 1: Write the failing test** (append)
```python
def test_smoke_check_passes_on_real_bundle(tmp_path):
    # build_one runs the smoke-check by default; a clean cursor bundle must pass
    out = build_one("cursor", out_root=tmp_path)   # raises if smoke fails
    assert (out / "SKILL.md").is_file()


def test_smoke_check_detects_broken_bundle(tmp_path):
    import pytest
    from generator.build_skill import _smoke_check
    out = build_one("cursor", out_root=tmp_path, smoke=False)
    # break the vendored core: remove providers_api so load_providers/import fails
    (out / "scripts" / "cld" / "providers_api.py").unlink()
    with pytest.raises(RuntimeError):
        _smoke_check(out)
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement**
  - `_smoke_check(out)`: run a subprocess `python -c "<probe>"` with `cwd = out/"scripts"` and `env` WITHOUT the monorepo on `PYTHONPATH` (pass `env={**os.environ, "PYTHONPATH": str(out/'scripts')}` so ONLY the vendored bundle resolves — and explicitly do NOT inherit the repo `engine` path; the subprocess cwd + PYTHONPATH point only at the vendored `scripts/`). The probe: `import cld; from cld.providers_api import load_providers, all_providers; load_providers(); ps=[p.name for p in all_providers()]; assert len(ps)==1, ps; from cld.models import render_chat_picker, recommend; recommend(available_ids=[]); print('SMOKE_OK')`. (Use `from cld.executors.opencode import _default_runner`-style imports ONLY if provider-agnostic — keep the probe provider-agnostic: just load_providers + assert one + a recommend/render call.) Capture stdout+stderr; if returncode != 0 or `SMOKE_OK` not in output → `raise RuntimeError(f"smoke-check failed for {out}:\n{output}")`.
  - `build_one(provider, *, out_root="dist", smoke=True)`: after compose+scaffold, `if smoke: _smoke_check(out)`. Add `--no-smoke` to `main` (sets `smoke=False`).
  - Note: earlier tasks' tests call `build_one(...)` which now runs the smoke-check by default — that's fine (it must pass on a real bundle). If any earlier unit test is slowed unacceptably, it may pass `smoke=False`, but prefer leaving smoke on (it's the proof).
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add generator/build_skill.py tests/test_generator.py
git commit -m "feat(generator): standalone smoke-check (vendored bundle imports + one provider + picker)"
```

---

## Done criteria (Sub-plan 2)
- `python generator/build_skill.py <provider>` (and `--all`) produces `dist/cross-llm-<provider>/` = SKILL.md (composed, banner, version) + references/examples + `scripts/{run_delivery.py(shim), cld/, cld_providers/<provider>/}` — trimmed (no other providers) + scaffolding (README/LICENSE/.gitignore).
- The bundle passes a standalone smoke-check (imports `cld`, `load_providers()` finds exactly one provider, picker renders) with ONLY the vendored bundle on the path — proving zero-install self-containment.
- Full suite green. Update STATUS.md: Sub-plan 2 done → Next = Sub-plan 3 (self-containment + generator tests), then SP4 (publishing).
- **Not here:** publishing to per-provider repos / the umbrella (Sub-plan 4); deeper generator/self-containment test matrix (Sub-plan 3).
