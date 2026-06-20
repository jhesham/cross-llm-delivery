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
    assert not (out / "scripts" / "cld_providers" / "gemini").exists()


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
