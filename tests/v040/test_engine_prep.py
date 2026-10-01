"""v0.4.0 engine preparation: final errors, Claude spec grammar, validation extra."""
from types import SimpleNamespace

import pytest

from cld.executors.base import FINAL_EXECUTOR_ERRORS, final_error_message
from cld.models import resolve_spec


@pytest.mark.parametrize("error,needle", [("usage_limit", "reset"),
                                          ("model_mismatch", "requested model"),
                                          ("not_logged_in", "claude auth login")])
def test_new_final_errors_are_final(error, needle):
    assert error in FINAL_EXECUTOR_ERRORS
    assert needle in final_error_message(error)


@pytest.mark.parametrize("spec", ["claude:sonnet@low", "claude:opus@high", "claude:Claude-Sonnet-5@low",
                                  "claude:claude-sonnet-5", "claude:claude-sonnet-5@ultra",
                                  "claude:claude-sonnet-5@low+fast"])
def test_claude_requires_exact_id_and_supported_effort(spec):
    # Must fail for the Claude-specific reason, not because the provider is unregistered.
    with pytest.raises(ValueError, match=r"exact model ID|explicit effort|Service tier suffix"):
        resolve_spec(spec)


def test_validation_extra_appends_provider_context():
    from cld.cli import _validation_extra
    with_extra = SimpleNamespace(context_extra=lambda: "claude-account:org:pro")
    without = SimpleNamespace(context_extra=None)
    assert _validation_extra("", with_extra) == "claude-account:org:pro"
    assert _validation_extra("user", with_extra) == "user\nclaude-account:org:pro"
    assert _validation_extra("user", without) == "user"
