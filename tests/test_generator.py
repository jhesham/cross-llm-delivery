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
