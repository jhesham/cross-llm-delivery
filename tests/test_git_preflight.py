"""Acceptance tests for the git preflight (first-run cliff).

Worktree isolation is step one of every slice. If git is missing, or the target --repo isn't
a git repository, the OLD behavior was a raw RuntimeError mid-build. The preflight must catch
both at build start with a friendly, actionable message — and must never block the no-dispatch
commands (--status/--dry-run) which don't need git.
"""
import skill.scripts.run_delivery as rd


def test_git_preflight_ok_when_git_and_repo_present(monkeypatch, tmp_path):
    monkeypatch.setattr(rd.shutil, "which", lambda c: "/usr/bin/git" if c == "git" else None)
    monkeypatch.setattr(rd, "_is_git_repo", lambda repo: True)
    assert rd._preflight_git(str(tmp_path)) is None


def test_git_preflight_message_when_git_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(rd.shutil, "which", lambda c: None)  # no git on PATH
    msg = rd._preflight_git(str(tmp_path))
    assert msg is not None
    assert "git" in msg.lower() and "install" in msg.lower()


def test_git_preflight_message_when_not_a_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(rd.shutil, "which", lambda c: "/usr/bin/git")
    monkeypatch.setattr(rd, "_is_git_repo", lambda repo: False)
    msg = rd._preflight_git(str(tmp_path))
    assert msg is not None
    assert "git init" in msg.lower() or "not a git repo" in msg.lower()


def test_step_aborts_before_dispatch_when_git_missing(tmp_path, monkeypatch, capsys):
    plan = tmp_path / "plan.md"
    plan.write_text("## SLICE: A\nbrief: b\nfiles: x.py\nacceptance_test_path: t.py\ndeps:\n",
                    encoding="utf-8")
    monkeypatch.setattr(rd.shutil, "which", lambda c: None)          # no git
    monkeypatch.setattr(rd, "_preflight_executor", lambda spec: None)  # isolate: executor OK

    def boom(*a, **k):
        raise AssertionError("must not dispatch when git preflight fails")

    monkeypatch.setattr(rd, "run_plan_parallel", boom)
    rc = rd.main([str(plan), "--repo", str(tmp_path), "--ledger", str(tmp_path / "l.json"),
                  "--executor", "opencode:opencode/glm-5.2", "--step"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "git" in out.lower() and "install" in out.lower()


def test_status_not_blocked_by_missing_git(tmp_path, monkeypatch):
    monkeypatch.setattr(rd.shutil, "which", lambda c: None)  # no git at all
    rc = rd.main(["--status", "--repo", str(tmp_path)])
    assert rc == 0
