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
