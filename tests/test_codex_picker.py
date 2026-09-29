import json

import pytest

from cld.models import build_model_index, pick_executor, render_model_level, spec_with_effort
from cld_providers.codex.catalog import list_codex_models


def catalog(*ids, efforts=("low", "medium", "max")):
    return json.dumps({"models": [dict(slug=id, display_name=id,
        visibility="list", default_reasoning_level="max",
        supported_reasoning_levels=[{"effort": e} for e in efforts]) for id in ids]})


def choices(raw):
    return build_model_index(opencode_ids=[], cursor_models=[], evidence={},
        codex_models=list_codex_models(runner=lambda a, c: (0, raw)))


def test_discovery_is_bounded_local_catalog_only():
    calls = []
    def runner(argv, cwd):
        calls.append(argv)
        return 0, catalog("gpt-6-astra", "gpt-5.6-terra")
    assert [m.id for m in list_codex_models(runner=runner)] == ["gpt-6-astra", "gpt-5.6-terra"]
    assert calls == [["codex", "debug", "models", "--bundled"]]


@pytest.mark.parametrize("raw", ["garbage", "[]", '{"models":{}}', '{"models":[null,42]}'])
def test_bad_catalog_does_not_fabricate_choices(raw):
    assert list_codex_models(runner=lambda a, c: (0, raw)) == []


def test_failed_discovery_leaves_explicit_id_escape_hatch():
    assert list_codex_models(runner=lambda a, c: (1, catalog("gpt-6-sol"))) == []
    spec = pick_executor([], index=[], input_fn=lambda _: "codex:gpt-6-sol@low",
        output_fn=lambda _: None)
    assert spec == "codex:gpt-6-sol@low"


def test_visibility_duplicate_ids_unknown_efforts_and_controls():
    rows = json.loads(catalog("gpt-6-sol"))["models"]
    rows += [dict(rows[0]), dict(rows[0], slug="hidden", visibility="hide"),
        dict(rows[0], slug="bad@max"), dict(rows[0], slug="bad\nname"),
        dict(rows[0], slug="unknown", supported_reasoning_levels=[{"effort":"future"}])]
    ms = list_codex_models(runner=lambda a, c: (0, json.dumps({"models": rows})))
    assert [m.id for m in ms] == ["gpt-6-sol"]


def test_cost_sensitive_default_is_explicit_and_untested_not_hidden():
    idx = choices(catalog("gpt-6-astra", "gpt-6-sol", "gpt-6-luna",
        "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"))
    lines, models = render_model_level(idx, executor="codex", provider="gpt", headless_only=False)
    assert len(models) == 6 and "untested" in "\n".join(lines)
    for m in models:
        assert m.default_effort == "low" and m.cost_class == "metered-unknown"
        assert spec_with_effort(m, "low") == m.spec + "@low"
        assert spec_with_effort(m, "max") == m.spec + "@max"
        assert spec_with_effort(m, None) == m.spec + "@low"


def test_model_only_evidence_does_not_claim_validated_effort_or_tier():
    ms = list_codex_models(runner=lambda a, c: (0, catalog("gpt-6-sol")))
    idx = build_model_index(opencode_ids=[], cursor_models=[], codex_models=ms,
        evidence={"codex:gpt-6-sol": "verified", "codex:gpt-6-sol@max+fast": "verified"})
    assert next(m for m in idx if m.executor == "codex").headless_status == "untested"


def test_no_implicit_high_or_max_when_low_medium_missing():
    m = next(m for m in choices(catalog("expensive-only", efforts=("max",))) if m.executor == "codex")
    assert m.default_effort is None
    with pytest.raises(ValueError, match="effort"):
        spec_with_effort(m, None)
    with pytest.raises(ValueError, match="effort"):
        spec_with_effort(m, "low")


@pytest.mark.parametrize("tier,suffix", [("", ""), ("2", "+fast")])
def test_cli_browse_codex_preserves_low_default_and_opt_in_tier(tier, suffix):
    idx = choices(catalog("gpt-6-astra"))
    # No shortlist: 1 Browse; executor 2 Codex (1 Antigravity); provider 1;
    # model 1; default effort; default or explicit fast tier.
    answers = iter(["1", "2", "1", "1", "", tier])
    out = []
    assert pick_executor([], index=idx, input_fn=lambda _: next(answers), output_fn=out.append) == "codex:gpt-6-astra@low" + suffix
    assert "untested" in "\n".join(out)


def test_invalid_browse_selection_never_silently_selects_workhorse():
    answers = iter(["1", "999"])
    with pytest.raises(ValueError, match="selection"):
        pick_executor([], index=choices(catalog("gpt-6-sol")),
            input_fn=lambda _: next(answers), output_fn=lambda _: None)


def test_medium_fallback_and_cp1252_safe_labels():
    data = json.loads(catalog("gpt-6-sol", efforts=("medium", "max")))
    data["models"][0]["display_name"] = "Sol \U0001f680"
    idx = choices(json.dumps(data))
    m = next(m for m in idx if m.executor == "codex")
    assert m.default_effort == "medium"
    assert spec_with_effort(m, None) == "codex:gpt-6-sol@medium"
    m.label.encode("cp1252")


def test_provider_discovery_does_not_create_a_static_default():
    from cld_providers.codex.provider import PROVIDER
    assert PROVIDER.catalog == () and PROVIDER.default_workhorse == ""
    assert PROVIDER.list_models(lambda a, c: (0, catalog("gpt-6-luna"))) == ["gpt-6-luna"]


def test_default_discovery_honors_probe_timeout(monkeypatch):
    from cld_providers.codex import catalog as module
    calls = []
    class Result:
        returncode = 0
        stdout = catalog("gpt-6-sol")
        error = None
    def process(argv, cwd, **kwargs):
        calls.append(kwargs)
        return Result()
    monkeypatch.setenv("CLD_PROBE_TIMEOUT", "1.5")
    monkeypatch.setattr(module, "run_process", process)
    assert module.list_codex_models()[0].id == "gpt-6-sol"
    assert calls == [{"timeout": 1.5}]


def test_interactive_cli_uses_discovered_codex_index(monkeypatch):
    from cld import cli, picker, models
    idx = choices(catalog("gpt-6-sol"))
    monkeypatch.setattr(picker, "discover_model_index", lambda: idx)
    def pick(recs, *, index):
        m = next(m for m in index if m.executor == "codex")
        return spec_with_effort(m, None)
    monkeypatch.setattr(models, "pick_executor", pick)
    assert cli.prompt_for_executor() == "codex:gpt-6-sol@low"


def test_json_picker_is_advisory_and_emits_canonical_default(monkeypatch, capsys):
    from cld import picker
    monkeypatch.setattr(picker, "discover_model_index", lambda: choices(catalog("gpt-6-sol")))
    assert picker.main(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["advisory"] is True and data["dispatches"] == 0
    m = next(m for m in data["models"] if m["executor"] == "codex")
    assert m["default_spec"] == "codex:gpt-6-sol@low"
    assert m["service_tiers"] == ["standard", "fast"]
    assert m["headless_status"] == "untested"
