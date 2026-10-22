"""v0.5.1 review (CODEX2): MCP overrides must be valid for Codex and cover project config layers."""
from tests.evidence._lazy import resolve
from tests.test_t16_codex_adapter import FakeCodexRunner, repo, task  # noqa: F401  (fixture)

C = "cld_providers.codex.contract"


def _values(argv):
    return [argv[i + 1] for i, a in enumerate(argv) if a in ("--config", "-c")]


def test_names_codex_cannot_override_are_skipped_not_emitted():
    values = _values(resolve(C, "isolation_args")(["docs", "team.docs", 'we"ird']))
    assert "mcp_servers.docs.enabled=false" in values
    assert not any("team" in v or "ird" in v for v in values), values


def test_worktree_project_mcp_servers_are_disabled(repo, tmp_path, monkeypatch):  # noqa: F811
    from cld_providers.codex.provider import CodexExecutor
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    (repo / ".codex").mkdir()
    (repo / ".codex" / "config.toml").write_text('[mcp_servers.project_docs]\ncommand = "x"\n', encoding="utf-8")
    runner = FakeCodexRunner()
    CodexExecutor(model="gpt-example", runner=runner).run(task(), repo)
    assert "mcp_servers.project_docs.enabled=false" in _values(runner.calls[-1][0])


def test_skipped_names_are_reported_in_the_run_log(repo, tmp_path, monkeypatch):  # noqa: F811
    from cld_providers.codex.provider import CodexExecutor
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text('[mcp_servers."team.docs"]\ncommand = "x"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    runner = FakeCodexRunner(write=lambda cwd: (cwd / "value.py").write_text("VALUE = 2\n", encoding="utf-8"))
    result = CodexExecutor(model="gpt-example", runner=runner).run(task(), repo)
    assert "team.docs" in result.raw_log
