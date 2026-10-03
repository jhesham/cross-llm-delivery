"""Independent review of provider-owned discovery and admission privacy."""
from dataclasses import replace
import os
from pathlib import Path

import pytest

from cld.admission import AdmissionBlocked
from cld import providers_api
from tests.test_n05_codex_config_identity import admission_setup, assert_blocked, SPEC


def test_native_managed_inputs_are_included(admission_setup, monkeypatch):
    env = admission_setup
    program_data = env.user / "program data"
    monkeypatch.setenv("ProgramData", str(program_data))
    descriptor = providers_api.get_provider("codex")
    inputs = set(descriptor.config_inputs(env.repo))
    assert (env.selected / "config.toml").resolve() in inputs
    assert (env.repo / ".codex/config.toml").resolve() in inputs
    assert (env.repo.parent / ".codex/config.toml").resolve() in inputs
    if os.name == "nt":
        assert (program_data / "OpenAI/Codex/config.toml").resolve() in inputs
        assert (program_data / "OpenAI/Codex/requirements.toml").resolve() in inputs
        assert (env.selected / "managed_config.toml").resolve() in inputs
        assert (env.user / ".codex/managed_config.toml").resolve() in inputs
    else:
        assert {Path("/etc/codex") / name for name in
                ("config.toml", "requirements.toml", "managed_config.toml")} <= inputs


def test_callback_selection_is_recomputed_for_admitted_factory(admission_setup, monkeypatch):
    env = admission_setup
    original = providers_api.get_provider("codex")
    selected = [env.repo / "one.toml"]
    selected[0].write_text('route = "one"\n')
    other = env.repo / "two.toml"
    other.write_text('route = "two"\n')
    callback = lambda repository: (*original.config_inputs(repository), selected[0])
    monkeypatch.setitem(providers_api._REGISTRY, "codex", replace(original, config_inputs=callback))
    factory = env.prepare()
    selected[0] = other
    assert_blocked(lambda: factory(SPEC), AdmissionBlocked, "changed after admission")


def test_missing_referenced_credential_becoming_present_invalidates(admission_setup, monkeypatch):
    env = admission_setup
    config = env.selected / "config.toml"
    config.write_text('[model_providers.gateway]\nenv_key = "N05_REVIEW_KEY"\n')
    monkeypatch.delenv("N05_REVIEW_KEY", raising=False)
    factory = env.prepare()
    env.args.validation_policy = "deny"
    monkeypatch.setenv("N05_REVIEW_KEY", "n05-review-private-value")
    assert_blocked(lambda: factory(SPEC), AdmissionBlocked, "changed after admission")
    assert_blocked(env.prepare, AdmissionBlocked)
    assert "n05-review-private-value" not in env.evidence.read_text()


@pytest.mark.parametrize("value", ["~/.codex", "", "relative-home"])
def test_home_must_be_absolute_before_tilde_expansion(admission_setup, monkeypatch, value):
    env = admission_setup
    monkeypatch.setenv("CODEX_HOME", value)
    failure = assert_blocked(env.prepare, ValueError)
    assert "CODEX_HOME" in str(failure) and "absolute" in str(failure)
    assert not env.validations and not env.creations


def test_unreadable_codex_input_fails_closed_without_parser_details(admission_setup, monkeypatch):
    env = admission_setup
    config = env.selected / "config.toml"
    config.write_text('model_provider = "gateway"\n')
    original = Path.open
    def unreadable(path, *args, **kwargs):
        if path.resolve() == config.resolve():
            raise PermissionError("n05-secret-must-not-appear-in-diagnostics")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", unreadable)
    failure = assert_blocked(env.prepare, ValueError)
    assert "n05-secret" not in str(failure)
    assert not env.validations and not env.creations
