from cld.models import ModelChoice, _provider_of


def test_modelchoice_fields():
    c = ModelChoice(spec="cursor:composer-2.5", executor="cursor", provider="other",
                    model="composer-2.5", label="Composer 2.5", cost_class="cheap-metered",
                    headless_status="untested", efforts=["low", "high"], default_effort="high")
    assert c.spec == "cursor:composer-2.5" and c.efforts == ["low", "high"]
    assert c.default_effort == "high"


def test_provider_of_recognizes_more_providers():
    assert _provider_of("opencode/grok-build-0.1") == "grok"
    assert _provider_of("opencode/kimi-k2.6") == "kimi"
    assert _provider_of("opencode/qwen3.5-plus") == "qwen"
    assert _provider_of("opencode/glm-5") == "glm"
    assert _provider_of("opencode/minimax-m2.5") == "minimax"
    assert _provider_of("opencode/claude-opus-4-8") == "claude"
    assert _provider_of("opencode/big-pickle") == "other"
