"""Real admission must bind Codex routing/configuration, without live inference."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cld import cli
from cld.admission import AdmissionBlocked
from cld.evidence import EvidenceStore
from cld.executors.base import SliceTask
from cld.validate import ValidationResult

SPEC = "codex:gpt-6-luna@max+fast"


@pytest.fixture
def admission_setup(tmp_path, monkeypatch):
    import cld.evidence as evidence
    import cld.validate as validation
    user = tmp_path / "user home"
    selected = tmp_path / "selected codex home"
    repo = tmp_path / "parent project" / "repo"
    for directory in (user / ".codex", selected, repo / ".codex"):
        directory.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: user))
    monkeypatch.setenv("CODEX_HOME", str(selected))
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)
    monkeypatch.delenv("CODEX_SANDBOX_NETWORK_DISABLED", raising=False)
    monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
    monkeypatch.setattr(evidence, "DEFAULT_PATH", tmp_path / "evidence.json")
    binary = tmp_path / "offline-codex.exe"
    binary.write_bytes(b"fixture binary identity")
    monkeypatch.setattr(cli, "_preflight_executor", lambda spec: None)
    monkeypatch.setattr(cli, "_resolve_cli", lambda command: str(binary))
    monkeypatch.setattr(cli, "build_rung_planner", lambda *a, **kw:
        lambda task: [("workhorse", SPEC, 0)])
    creations, validations = [], []
    def executor(*a, **kw):
        creations.append((a, kw))
        return "OFFLINE_EXECUTOR"
    def validate(spec, **kw):
        validations.append(spec)
        return ValidationResult(spec, True, "verified", 0)
    monkeypatch.setattr(cli, "get_executor", executor)
    monkeypatch.setattr(validation, "validate_model", validate)
    args = SimpleNamespace(repo=str(repo), worktree_root=None, step=False,
        executor=SPEC, validation_policy="allow", validation_max_age=86400,
        revalidate_models=False, validation_config=[], validation_context="")
    ledger = SimpleNamespace(build={"run_id": "5" * 32}, is_done=lambda sid: False,
                             get=lambda sid: None)
    tasks = [SliceTask("N05", "work", ["value.py"], "test_value.py")]
    def prepare():
        return cli.prepare_dispatch(args, tasks, ledger)[0]
    return SimpleNamespace(repo=repo, user=user, selected=selected, args=args,
        prepare=prepare, creations=creations, validations=validations,
        evidence=tmp_path / "evidence.json")


@pytest.mark.parametrize("location", ["selected-home", "default-home", "project", "ancestor"])
@pytest.mark.parametrize("change", ["edit", "create", "delete"])
def test_config_change_blocks_saved_evidence_and_already_admitted_factory(admission_setup, monkeypatch, location, change):
    env = admission_setup
    if location == "default-home":
        monkeypatch.delenv("CODEX_HOME")
        config = env.user / ".codex/config.toml"
    elif location == "selected-home":
        config = env.selected / "config.toml"
    elif location == "project":
        config = env.repo / ".codex/config.toml"
    else:
        config = env.repo.parent / ".codex/config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    first = 'model_provider = "route_a"\n# n05-secret-that-must-not-be-persisted\n'
    if change != "create":
        config.write_text(first, encoding="utf-8")
    factory = env.prepare()
    assert env.validations == [SPEC]
    env.args.validation_policy = "deny"
    assert env.prepare()(SPEC) == "OFFLINE_EXECUTOR"
    env.creations.clear()
    if change == "delete":
        config.unlink()
    else:
        config.write_text('model_provider = "route_b"\n', encoding="utf-8")
    with pytest.raises(AdmissionBlocked, match="changed after admission"):
        factory(SPEC)
    with pytest.raises(AdmissionBlocked):
        env.prepare()
    assert not env.creations, "Configuration drift reached executor construction"
    assert env.validations == [SPEC], "Deny must block before validation spend"
    assert "n05-secret" not in env.evidence.read_text(encoding="utf-8")
    reports = list((env.repo / ".cld").rglob("admission.json"))
    assert reports and all("n05-secret" not in p.read_text(encoding="utf-8") for p in reports)


@pytest.mark.parametrize("reference", ["env_key", "env_http_headers"])
def test_config_referenced_environment_values_key_evidence(admission_setup, monkeypatch, reference):
    env = admission_setup
    if reference == "env_key":
        setting = 'env_key = "N05_GATEWAY_SECRET"'
    else:
        setting = 'env_http_headers = { "X-Route" = "N05_GATEWAY_SECRET" }'
    (env.selected / "config.toml").write_text('[model_providers.gateway]\n' + setting + '\n', encoding="utf-8")
    monkeypatch.setenv("N05_GATEWAY_SECRET", "n05-hidden-before")
    factory = env.prepare()
    env.args.validation_policy = "deny"
    monkeypatch.setenv("N05_GATEWAY_SECRET", "n05-hidden-after")
    with pytest.raises(AdmissionBlocked, match="changed after admission"):
        factory(SPEC)
    with pytest.raises(AdmissionBlocked):
        env.prepare()
    record = EvidenceStore(env.evidence).get(SPEC)
    assert "N05_GATEWAY_SECRET" in record["context"]["env_names"]
    assert "n05-hidden" not in json.dumps(record)
    assert env.validations == [SPEC]


def test_selected_home_does_not_hash_unused_default_home(admission_setup):
    env = admission_setup
    (env.selected / "config.toml").write_text('model_provider = "selected"\n')
    unused = env.user / ".codex/config.toml"
    unused.write_text('model_provider = "unused"\n')
    factory = env.prepare()
    env.args.validation_policy = "deny"
    unused.write_text('model_provider = "still-unused"\n')
    assert factory(SPEC) == "OFFLINE_EXECUTOR"
    assert env.prepare()(SPEC) == "OFFLINE_EXECUTOR"
    assert env.validations == [SPEC]


def test_explicit_inputs_are_merged_with_automatic_codex_inputs(admission_setup):
    env = admission_setup
    extra = env.repo / "gateway-settings.toml"
    extra.write_text('route = "one"\n')
    env.args.validation_config = [str(extra)]
    factory = env.prepare()
    extra.write_text('route = "two"\n')
    with pytest.raises(AdmissionBlocked, match="changed after admission"):
        factory(SPEC)
