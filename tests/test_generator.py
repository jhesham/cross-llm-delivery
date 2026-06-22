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


# ---- Task 2: vendor + trim ----

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
    assert not (out / "scripts" / "cld_providers" / "antigravity").exists()


def test_vendors_driver_with_syspath_shim(tmp_path):
    out = _build(tmp_path, "cursor")
    drv = (out / "scripts" / "run_delivery.py").read_text(encoding="utf-8")
    assert "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))" in drv


def test_vendors_references(tmp_path):
    out = _build(tmp_path, "cursor")
    assert (out / "references" / "authoring-plans.md").is_file()


# ---- Task 3: core SKILL template ----

def test_skill_template_exists_with_placeholders():
    from pathlib import Path
    t = Path("skill/SKILL.template.md").read_text(encoding="utf-8")
    for ph in ("{{PROVIDER_NAME}}", "{{DEFAULT_WORKHORSE}}", "{{PROVIDER_FRAGMENT}}",
               "{{SETUP}}", "{{BANNER}}"):
        assert ph in t
    # the core template must NOT hardcode a specific provider in its prose
    low = t.lower()
    assert "opencode" not in low and "composer" not in low


# ---- Task 4: SKILL compose + banner + VERSION + repo scaffolding ----

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


# ---- Task 5: standalone smoke-check ----

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


# ---- Task 1 (SP3): trim non-active executor shims ----

import subprocess, sys, os


def test_trimmed_bundle_has_no_dead_provider_imports(tmp_path):
    # every vendored module must import cleanly in isolation (no absent-provider ImportError)
    out = build_one("cursor", out_root=tmp_path)            # smoke already runs; this is stricter
    scripts = out / "scripts"
    probe = (
        "import importlib, pkgutil\n"
        "import cld, cld_providers\n"
        "mods=[]\n"
        "for pkg in (cld, cld_providers):\n"
        "    for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__+'.'):\n"
        "        mods.append(m.name)\n"
        "bad=[]\n"
        "for name in mods:\n"
        "    try: importlib.import_module(name)\n"
        "    except Exception as e: bad.append((name, type(e).__name__, str(e)))\n"
        "assert not bad, bad\n"
        "print('IMPORTS_OK', len(mods))\n"
    )
    r = subprocess.run([sys.executable, "-c", probe], cwd=scripts,
                       env={**os.environ, "PYTHONPATH": str(scripts.resolve())},
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert "IMPORTS_OK" in (r.stdout + r.stderr), (r.stdout + r.stderr)


def test_active_provider_executor_shim_kept(tmp_path):
    # the active provider's own executor shim must REMAIN (it re-exports the vendored provider)
    out = build_one("cursor", out_root=tmp_path)
    ex = out / "scripts" / "cld" / "executors"
    assert (ex / "cursor.py").is_file()                 # active shim kept
    assert (ex / "base.py").is_file() and (ex / "__init__.py").is_file()
    assert not (ex / "opencode.py").exists()            # non-active shim trimmed


# ---- Task 2 (SP3): end-to-end self-containment via vendored driver ----

def test_vendored_driver_runs_dry_run_in_isolation(tmp_path):
    out = build_one("antigravity", out_root=tmp_path)
    scripts = out / "scripts"
    plan = tmp_path / "p.md"
    plan.write_text(
        "## SLICE: T1\nbrief: do x\nfiles: src/x.py\nacceptance_test_path: tests/test_x.py\ndeps:\n",
        encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(scripts / "run_delivery.py"), str(plan), "--dry-run"],
        cwd=scripts,
        env={**__import__('os').environ, "PYTHONPATH": str(scripts.resolve())},
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, (r.stdout + r.stderr)
    assert "T1" in (r.stdout + r.stderr)          # the dry-run printed the layer/schedule


# ---- Task 3 (SP3): cross-provider regression ----

def test_build_all_generates_every_provider(tmp_path):
    from generator.build_skill import build_one, _known_providers
    for p in _known_providers():
        out = build_one(p, out_root=tmp_path)
        assert (out / "SKILL.md").is_file()
        assert (out / "scripts" / "cld_providers" / p / "provider.py").is_file()
        # each is trimmed to its own provider only
        others = [q for q in _known_providers() if q != p]
        for q in others:
            assert not (out / "scripts" / "cld_providers" / q).exists()
