"""v0.5.1 review (INSTALLER2): the copy fallback owns only what it created and always restores the backup."""
from pathlib import Path

import pytest

from tests.test_t13a_install import bundle, invoke
from tests.v051._red import must


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


def test_failed_cleanup_still_restores_backup_and_keeps_original_error(tmp_path, monkeypatch):
    from generator import install_codex
    source = bundle(tmp_path)
    scope = tmp_path / "project"
    target = scope / ".agents" / "skills" / source.name
    assert invoke(scope, "--install", source=source)[0] == 0
    (source / "scripts" / "run_delivery.py").write_text("print('new')\n", encoding="utf-8")
    _deny_stage_rename(monkeypatch)
    original_copytree, original_rmtree = install_codex.shutil.copytree, install_codex.shutil.rmtree

    def copytree(src, dst, *args, **kwargs):
        if ".cld-stage-" in Path(src).name:
            Path(dst).mkdir(parents=True, exist_ok=True)
            (Path(dst) / "partial.txt").write_text("partial", encoding="utf-8")
            raise OSError("copy failed midway")
        return original_copytree(src, dst, *args, **kwargs)

    def rmtree(path, *args, **kwargs):
        if Path(path) == target and (Path(path) / "partial.txt").exists():
            raise PermissionError(32, "file is locked")
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_codex.shutil, "copytree", copytree)
    monkeypatch.setattr(install_codex.shutil, "rmtree", rmtree)
    error = None
    try:
        install_codex._install(source, scope, target, source.name)
    except Exception as exc:
        error = exc
    assert error is not None and "copy failed midway" in str(error), error
    must(install_codex._verify_owned, target)
    assert "ok" in (target / "scripts" / "run_delivery.py").read_text(encoding="utf-8")
