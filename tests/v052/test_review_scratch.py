"""v0.5.2 review (CODEXSCRATCH): command output goes to a private scratch folder outside the worktree,
granted as a writable root, so it can never collide with tracked files or enter the candidate diff."""
from pathlib import Path

from tests.evidence._lazy import resolve
from tests.test_t16_codex_adapter import FakeCodexRunner, repo, task  # noqa: F401  (fixture)
from tests.v051._red import must

C = "cld_providers.codex.contract"


def _values(argv):
    return [argv[i + 1] for i, a in enumerate(argv) if a in ("--config", "-c")]


def test_invocation_grants_and_names_the_scratch_folder(tmp_path):
    ws, scratch = tmp_path / "ws", tmp_path / "scratch"
    ws.mkdir()
    (ws / ".git").mkdir()
    scratch.mkdir()
    call = must(resolve(C, "build_invocation"), "gpt-example", ws, "p", scratch_dir=scratch)
    roots = [v for v in _values(call.argv) if v.startswith("sandbox_workspace_write.writable_roots=")]
    assert roots and scratch.as_posix() in roots[0].replace("\\\\", "/").replace("\\", "/"), roots
    assert call.env.get("CLD_SCRATCH_DIR") == str(scratch)
    assert str(scratch) in call.stdin


def test_role_never_suggests_writing_output_into_the_worktree(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / ".git").mkdir()
    text = resolve(C, "build_invocation")("gpt-example", ws, "p").stdin.lower()
    assert "cld-test-output.txt" not in text and "inside the working directory" not in text


def test_dispatch_uses_a_scratch_folder_outside_the_worktree_and_removes_it(repo):  # noqa: F811
    from cld_providers.codex.provider import CodexExecutor
    seen = {}

    def write(cwd):
        seen["env"] = dict(runner.calls[-1][2].get("env") or {})
        value = seen["env"].get("CLD_SCRATCH_DIR")
        scratch = Path(value) if value else None
        seen["scratch"] = scratch
        if scratch is not None and scratch.is_dir():
            (scratch / "out.txt").write_text("1 passed", encoding="utf-8")
        (cwd / "value.py").write_text("VALUE = 2\n", encoding="utf-8")

    runner = FakeCodexRunner(write=write)
    result = CodexExecutor(model="gpt-example", runner=runner).run(task(), repo)
    scratch = seen.get("scratch")
    assert scratch and str(scratch) not in ("", "."), seen
    assert not scratch.resolve().is_relative_to(repo.resolve()), "scratch folder must be outside the worktree"
    assert result.ok and result.files_changed == ["value.py"], (result.files_changed, result.raw_log[-300:])
    assert not scratch.exists(), "scratch folder must be removed after the dispatch"
