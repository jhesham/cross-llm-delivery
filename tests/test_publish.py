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
