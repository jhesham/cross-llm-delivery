"""Codex records `[projects.'<dir>'] trust_level` in config.toml whenever it runs in a new
directory, including CLD's own validation probe folder. Those entries must not change the
validation identity, or every first validation blocks with "changed during validation" and each
retry pays for another probe. Every other config change must still change the identity."""
from cld.admission import AdmissionBlocked
from cld.validate import ValidationResult

from tests.test_n05_codex_config_identity import SPEC, admission_setup, assert_blocked  # noqa: F401

TRUST = "\n[projects.'c:\\\\tmp\\\\probe-{n}\\\\repo']\ntrust_level = \"trusted\"\n"


def test_trust_entry_written_during_validation_still_admits(admission_setup, monkeypatch):
    import cld.validate as validation
    env = admission_setup
    config = env.selected / "config.toml"
    config.write_text('model_provider = "openai"\n')
    calls = []

    def validate(spec, **kw):
        calls.append(spec)
        config.write_text(config.read_text() + TRUST.format(n=1))
        return ValidationResult(spec, True, "verified", 0)

    monkeypatch.setattr(validation, "validate_model", validate)
    env.prepare()
    assert calls == [SPEC]


def test_trust_entry_added_later_reuses_saved_evidence(admission_setup, monkeypatch):
    import cld.validate as validation
    env = admission_setup
    config = env.selected / "config.toml"
    config.write_text('model_provider = "openai"\n')
    calls = []

    def validate(spec, **kw):
        calls.append(spec)
        return ValidationResult(spec, True, "verified", 0)

    monkeypatch.setattr(validation, "validate_model", validate)
    env.prepare()
    config.write_text(config.read_text() + TRUST.format(n=2))
    env.prepare()
    assert calls == [SPEC], "a new trust entry must not force a second paid probe"


def test_real_config_change_alongside_trust_entry_still_blocks(admission_setup, monkeypatch):
    import cld.validate as validation
    env = admission_setup
    config = env.selected / "config.toml"
    config.write_text('model_provider = "before"\n')

    def validate(spec, **kw):
        config.write_text('model_provider = "after"\n' + TRUST.format(n=3))
        return ValidationResult(spec, True, "verified", 0)

    monkeypatch.setattr(validation, "validate_model", validate)
    assert_blocked(env.prepare, AdmissionBlocked, "changed during validation")


def test_project_scoped_settings_other_than_trust_still_count(admission_setup, monkeypatch):
    import cld.validate as validation
    env = admission_setup
    config = env.selected / "config.toml"
    config.write_text('model_provider = "openai"\n')

    def validate(spec, **kw):
        config.write_text(config.read_text() + "\n[projects.'c:\\\\tmp\\\\x']\nmodel = \"other\"\n")
        return ValidationResult(spec, True, "verified", 0)

    monkeypatch.setattr(validation, "validate_model", validate)
    assert_blocked(env.prepare, AdmissionBlocked, "changed during validation")
