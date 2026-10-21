"""v0.5 review fix (CODEXGIT): evidence runs outside Git need --skip-git-repo-check."""
from tests.evidence._lazy import resolve

C = "cld_providers.codex.contract"


def test_evidence_invocation_outside_git_skips_repo_check(tmp_path):
    call = resolve(C, "build_invocation")("gpt-example", tmp_path, "answer", evidence=True)
    assert "--skip-git-repo-check" in call.argv
    assert call.argv[-1] == "-"


def test_code_invocations_never_skip_repo_check(tmp_path):
    (tmp_path / ".git").mkdir()
    build = resolve(C, "build_invocation")
    for kwargs in ({}, {"full_access": True}):
        assert "--skip-git-repo-check" not in build("gpt-example", tmp_path, "p", **kwargs).argv
