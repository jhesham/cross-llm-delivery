"""v0.5.1 INSTALLER: a denied atomic rename falls back to a verified copy for fresh installs only;
an update keeps (restores) the previous installation and asks the user to retry."""
from pathlib import Path

import pytest

from tests.test_t13a_install import bundle, invoke
from tests.v051._red import must


def _deny_stage_rename(monkeypatch):
    original = Path.replace

    def replace(self, target):
        if ".cld-stage-" in self.name:
            raise PermissionError(5, "Access is denied")
        return original(self, target)

    monkeypatch.setattr(Path, "replace", replace)


def test_fresh_install_falls_back_to_copy_when_rename_is_denied(tmp_path, monkeypatch):
    from generator import install_codex
    source = bundle(tmp_path)
    scope = tmp_path / "project"
    target = scope / ".agents" / "skills" / source.name
    _deny_stage_rename(monkeypatch)
    result = must(install_codex._install, source, scope, target, source.name)
    assert result["outcome"] == "installed"
    install_codex._verify_owned(target)
    assert not any(".cld-stage-" in p.name for p in target.parent.iterdir())


def test_update_with_denied_rename_keeps_previous_install_and_never_copies(tmp_path, monkeypatch):
    from generator import install_codex
    source = bundle(tmp_path)
    scope = tmp_path / "project"
    target = scope / ".agents" / "skills" / source.name
    assert invoke(scope, "--install", source=source)[0] == 0
    (source / "scripts" / "run_delivery.py").write_text("print('new')\n", encoding="utf-8")
    _deny_stage_rename(monkeypatch)
    copies = []
    original_copytree = install_codex.shutil.copytree

    def copytree(src, dst, *args, **kwargs):
        if ".cld-stage-" in Path(src).name:
            copies.append(dst)
        return original_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr(install_codex.shutil, "copytree", copytree)
    error = None
    try:
        install_codex._install(source, scope, target, source.name)
    except Exception as exc:
        error = exc
    assert error is not None and "retry" in str(error).lower(), error
    assert copies == [], "an update must not fall back to copying"
    must(install_codex._verify_owned, target)
    assert "ok" in (target / "scripts" / "run_delivery.py").read_text(encoding="utf-8")
    leftovers = [p.name for p in target.parent.iterdir() if ".cld-" in p.name]
    assert leftovers == [], leftovers


def test_fresh_fallback_copy_failure_leaves_no_target(tmp_path, monkeypatch):
    from generator import install_codex
    source = bundle(tmp_path)
    scope = tmp_path / "project"
    target = scope / ".agents" / "skills" / source.name
    _deny_stage_rename(monkeypatch)
    original_copytree = install_codex.shutil.copytree

    def copytree(src, dst, *args, **kwargs):
        if ".cld-stage-" in Path(src).name:
            raise OSError("disk full")
        return original_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr(install_codex.shutil, "copytree", copytree)
    with pytest.raises(OSError):
        install_codex._install(source, scope, target, source.name)
    assert not target.exists()
