"""v0.5.1 review (INSTALLER2): the copy fallback owns only what it created and always restores the backup."""
from pathlib import Path

import pytest

from tests.test_t13a_install import bundle


def _deny_stage_rename(monkeypatch, on_deny=None):
    original = Path.replace

    def replace(self, target):
        if ".cld-stage-" in self.name:
            if on_deny:
                on_deny()
            raise PermissionError(5, "Access is denied")
        return original(self, target)

    monkeypatch.setattr(Path, "replace", replace)


def test_never_deletes_a_target_another_process_created(tmp_path, monkeypatch):
    from generator import install_codex
    source = bundle(tmp_path)
    scope = tmp_path / "project"
    target = scope / ".agents" / "skills" / source.name

    _deny_stage_rename(monkeypatch)
    original_copytree = install_codex.shutil.copytree

    def racing_copytree(src, dst, *args, **kwargs):
        if ".cld-stage-" in Path(src).name:
            # Another process creates the target after the vacancy check; the copy
            # then fails while still reading its source, before creating dst.
            Path(dst).mkdir(parents=True, exist_ok=True)
            (Path(dst) / "theirs.txt").write_text("foreign", encoding="utf-8")
            raise OSError("cannot read source entry")
        return original_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr(install_codex.shutil, "copytree", racing_copytree)
    with pytest.raises(Exception):
        install_codex._install(source, scope, target, source.name)
    assert (target / "theirs.txt").is_file(), "the fallback deleted a target it did not create"
