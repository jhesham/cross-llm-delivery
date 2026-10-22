"""v0.5.1 review 2 (GATEWAY3): managed settings override inherited environment, so they set the gateway identity."""
import json

from tests.evidence._lazy import resolve
from tests.v051._red import must

P = "cld_providers.claude.preflight"
ENV = {"ANTHROPIC_BASE_URL": "https://env.example.invalid", "ANTHROPIC_AUTH_TOKEN": "x"}


def _managed(tmp_path, url):
    path = tmp_path / "managed.json"
    path.write_text(json.dumps({"env": {"ANTHROPIC_BASE_URL": url}}), encoding="utf-8")
    return path


def _host(tmp_path, url):
    host, problem = must(resolve(P, "resolve_gateway"), "gateway", ENV, user_settings=tmp_path / "none.json",
                         managed_settings=_managed(tmp_path, url))
    assert problem is None, problem
    return host


def test_managed_gateway_wins_over_environment(tmp_path):
    assert _host(tmp_path, "https://managed-a.example.invalid") == "managed-a.example.invalid"


def test_changing_the_managed_gateway_changes_identity(tmp_path):
    context = resolve(P, "account_context")
    status = resolve(P, "AuthStatus")(logged_in=True, auth_method="oauth_token", org_id=None, subscription_type=None)
    a = context(status, mode="gateway", gateway=_host(tmp_path, "https://managed-a.example.invalid"))
    b = context(status, mode="gateway", gateway=_host(tmp_path, "https://managed-b.example.invalid"))
    assert a != b
