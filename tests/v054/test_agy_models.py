"""v0.5.4 AGYMODELS: Antigravity's catalog, discovery and cost class match current agy."""
from pathlib import Path

from tests.evidence._lazy import resolve

ROOT = Path(__file__).resolve().parents[2]
PROVIDER_MODULE = "cld_providers.antigravity.provider"

# Verbatim `agy models` output (agy 1.5.1): "<slug>\t<label>" after a status line.
AGY_MODELS_OUTPUT = """Fetching available models...
gemini-4-argon-medium\tGemini 4 Argon (Medium)
gemini-4-argon-high\tGemini 4 Argon (High)
gemini-4-argon-low\tGemini 4 Argon (Low)
gemini-3.8-flash-high\tGemini 3.8 Flash (High)
gemini-3.8-flash-medium\tGemini 3.8 Flash (Medium)
gemini-3.8-flash-low\tGemini 3.8 Flash (Low)
claude-opus-5-5-low\tClaude Opus 5.5 (Low)
claude-opus-5-5-medium\tClaude Opus 5.5 (Medium)
claude-opus-5-5-high\tClaude Opus 5.5 (High)
claude-sonnet-5-5-low\tClaude Sonnet 5.5 (Low)
claude-sonnet-5-5-medium\tClaude Sonnet 5.5 (Medium)
claude-sonnet-5-5-high\tClaude Sonnet 5.5 (High)
gpt-oss-120b-medium\tGPT-OSS 120B (Medium)
"""
CURRENT_LABELS = [line.split("\t", 1)[1] for line in AGY_MODELS_OUTPUT.splitlines()[1:]]
CATALOG_LABELS = {
    "Gemini 3.8 Flash (Low)", "Gemini 3.8 Flash (Medium)", "Gemini 3.8 Flash (High)",
    "Gemini 4 Argon (Low)", "Gemini 4 Argon (High)", "GPT-OSS 120B (Medium)",
    "Claude Sonnet 5.5 (High)", "Claude Opus 5.5 (High)",
}


def _provider():
    return resolve(PROVIDER_MODULE, "PROVIDER")


def test_list_agy_models_parses_labels_from_agy_models():
    list_agy_models = resolve(PROVIDER_MODULE, "list_agy_models")
    calls = []

    def runner(args, cwd, **_options):
        calls.append(list(args))
        return (0, AGY_MODELS_OUTPUT)

    assert list_agy_models(runner) == CURRENT_LABELS
    assert calls and calls[0][-1] == "models", calls


def test_list_agy_models_falls_back_to_the_catalog_when_agy_fails():
    list_agy_models = resolve(PROVIDER_MODULE, "list_agy_models")
    labels = list_agy_models(lambda args, cwd, **_o: (1, "boom"))
    assert set(labels) == CATALOG_LABELS, labels


def test_catalog_and_default_track_current_agy():
    provider = _provider()
    labels = {m.id.split(":", 1)[1] for m in provider.catalog}
    assert labels == CATALOG_LABELS, labels
    assert labels <= set(CURRENT_LABELS)
    assert provider.default_workhorse == "antigravity:Gemini 4 Argon (High)"
    assert all(m.cost_class == "flat" for m in provider.catalog)


def test_uncatalogued_antigravity_models_are_flat_but_other_providers_stay_unknown():
    resolve("cld.providers_api", "load_providers")()
    model_policy = resolve("cld.models", "model_policy")
    assert model_policy("antigravity:gemini-4-argon-medium")[1] == "flat"
    assert model_policy("antigravity:Gemini 4 Argon (Medium)")[1] == "flat"
    assert model_policy("opencode:opencode/not-a-real-model")[1] == "metered-unknown"


def test_model_index_lists_discovered_antigravity_models_as_flat():
    import inspect
    build_model_index = resolve("cld.models", "build_model_index")
    assert "antigravity_models" in inspect.signature(build_model_index).parameters
    rows =build_model_index(opencode_ids=[], cursor_models=[], evidence={},
                             antigravity_models=["Gemini 3.8 Flash (Low)", "Gemini 4 Argon (Medium)"])
    by_spec = {r.spec: r for r in rows}
    for spec in ("antigravity:Gemini 3.8 Flash (Low)", "antigravity:Gemini 4 Argon (Medium)"):
        assert spec in by_spec, sorted(by_spec)
        assert by_spec[spec].cost_class == "flat" and by_spec[spec].executor == "antigravity"


def test_picker_discovers_antigravity_models(monkeypatch):
    import importlib
    agy = importlib.import_module(PROVIDER_MODULE)
    monkeypatch.setattr(agy, "list_agy_models", lambda runner: ["Gemini 3.8 Flash (High)"], raising=False)
    monkeypatch.setattr(importlib.import_module("cld_providers.opencode.provider"),
                        "list_models", lambda runner: [])
    monkeypatch.setattr(importlib.import_module("cld_providers.cursor.provider"),
                        "list_cursor_models", lambda runner: [])
    discover = resolve("cld.picker", "discover_model_index")
    specs = {r.spec for r in discover()}
    assert "antigravity:Gemini 3.8 Flash (High)" in specs, sorted(specs)


def test_provider_docs_name_current_models_only():
    base = ROOT / "engine" / "cld_providers" / "antigravity"
    for name in ("SKILL.fragment.md", "setup.md"):
        text = (base / name).read_text(encoding="utf-8")
        for stale in ("Gemini 3.1", "Gemini 3.5", "4.6 (Thinking)"):
            assert stale not in text, (name, stale)
    assert "Gemini 4 Argon (High)" in (base / "SKILL.fragment.md").read_text(encoding="utf-8")
    assert "interactive terminal" not in (base / "setup.md").read_text(encoding="utf-8")
