"""v0.5.1 CODEXISO: executors run without the user's plugins, apps, MCP servers or test caches."""
from tests.evidence._lazy import resolve
from tests.test_t16_codex_adapter import FakeCodexRunner, repo, task  # noqa: F401  (fixture)

C = "cld_providers.codex.contract"
ESSENTIAL = ("shell_tool", "unified_exec", "fast_mode", "apply_patch_freeform")


def _config_values(argv):
    return [argv[i + 1] for i, a in enumerate(argv) if a in ("--config", "-c")]


def _codex_home(tmp_path, body):
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(body, encoding="utf-8")
    return home


def test_isolation_disables_nonessential_features_and_each_mcp_server():
    args = resolve(C, "isolation_args")(["docs", "warehouse-tools"])
    values = _config_values(args)
    for feature in ("plugins", "apps", "memories", "hooks", "skill_search", "computer_use", "browser_use"):
        assert f"features.{feature}=false" in values, feature
    assert not any(v.startswith(f"features.{f}=") for f in ESSENTIAL for v in values)
    assert "mcp_servers.docs.enabled=false" in values
    assert "mcp_servers.warehouse-tools.enabled=false" in values


def test_configured_mcp_servers_reads_names_only(tmp_path):
    home = _codex_home(tmp_path, '[mcp_servers.docs]\ncommand = "docs-server"\nenv = { TOKEN = "s3cret" }\n'
                                 '[mcp_servers.repo]\nurl = "https://mcp.example.invalid"\n'
                                 '[model_providers.gw]\nbase_url = "https://gw.example.invalid"\n')
    assert sorted(resolve(C, "configured_mcp_servers")(home)) == ["docs", "repo"]


def test_configured_mcp_servers_tolerates_missing_or_invalid_config(tmp_path):
    read = resolve(C, "configured_mcp_servers")
    assert read(tmp_path / "absent") == []
    assert read(_codex_home(tmp_path, "this is [not toml")) == []


def test_invocation_env_suppresses_bytecode_and_pytest_cache(tmp_path):
    (tmp_path / ".git").mkdir()
    call = resolve(C, "build_invocation")("gpt-example", tmp_path, "p")
    assert call.env.get("PYTHONDONTWRITEBYTECODE") == "1"
    assert "-p no:cacheprovider" in call.env.get("PYTEST_ADDOPTS", "")


def test_role_tells_windows_executors_to_run_tests_through_cmd(tmp_path):
    (tmp_path / ".git").mkdir()
    stdin = resolve(C, "build_invocation")("gpt-example", tmp_path, "p").stdin
    assert "cmd /c" in stdin


def test_executor_dispatch_carries_isolation(repo, tmp_path, monkeypatch):  # noqa: F811
    from cld_providers.codex.provider import CodexExecutor
    monkeypatch.setenv("CODEX_HOME", str(_codex_home(tmp_path, '[mcp_servers.docs]\ncommand = "x"\n')))
    runner = FakeCodexRunner()
    CodexExecutor(model="gpt-example", runner=runner).run(task(), repo)
    argv = runner.calls[-1][0]
    values = _config_values(argv)
    assert "features.plugins=false" in values and "mcp_servers.docs.enabled=false" in values
    assert argv[-1] == "-"
