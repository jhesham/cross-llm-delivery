"""CLD slice PREFLIGHT: model-free subscription login checks. Red by AssertionError only."""
import importlib
import json

AUTH = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty",
        "orgId": "org-123", "subscriptionType": "pro"}


def _preflight():
    try:
        module = importlib.import_module("cld_providers.claude.preflight")
    except ImportError:
        module = None
    assert module is not None, "cld_providers.claude.preflight not implemented"
    return module


def test_parse_subscription_status():
    status = _preflight().parse_auth_status(json.dumps(AUTH))
    assert (status.logged_in, status.auth_method, status.org_id, status.subscription_type) == (
        True, "claude.ai", "org-123", "pro")


def test_parse_rejects_malformed():
    module = _preflight()
    for text in ("", "not json", json.dumps({"authMethod": "claude.ai"}), json.dumps([1])):
        try:
            module.parse_auth_status(text)
        except ValueError:
            continue
        assert False, f"accepted {text!r}"


def test_auth_problem_cases():
    module = _preflight()
    ok = module.parse_auth_status(json.dumps(AUTH))
    assert module.auth_problem(ok) is None
    logged_out = module.parse_auth_status(json.dumps({**AUTH, "loggedIn": False}))
    assert "claude auth login" in module.auth_problem(logged_out)
    api_key = module.parse_auth_status(json.dumps({**AUTH, "authMethod": "api_key"}))
    problem = module.auth_problem(api_key)
    assert "subscription" in problem and "api_key" in problem


def test_account_context():
    module = _preflight()
    assert module.account_context(module.parse_auth_status(json.dumps(AUTH))) == "claude-account:org-123:pro"
    bare = module.parse_auth_status(json.dumps({"loggedIn": True, "authMethod": "claude.ai"}))
    assert module.account_context(bare) == "claude-account:unknown:unknown"


def test_run_auth_preflight():
    module = _preflight()
    calls = []

    def runner(argv, cwd):
        calls.append(argv)
        return 0, json.dumps(AUTH)

    status, problem = module.run_auth_preflight(runner, "/abs/claude.exe")
    assert calls == [["/abs/claude.exe", "auth", "status"]]
    assert status.org_id == "org-123" and problem is None
    status, problem = module.run_auth_preflight(lambda argv, cwd: (1, "boom"), "claude")
    assert status is None and "claude auth status" in problem
    status, problem = module.run_auth_preflight(lambda argv, cwd: (0, "garbage"), "claude")
    assert status is None and "claude auth status" in problem
