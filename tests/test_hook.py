"""T6.3: opt-in enforcement-hook decision logic.

The hook is *advisory and opt-in* — it never auto-installs. Its core is a PURE,
deliberately CONSERVATIVE classifier: when unsure, it does NOT route (so it can
never hijack a normal edit). These tests pin that conservatism.
"""

from cld.hook import HookDecision, should_route_to_executor


def test_defaults_to_not_routing_on_empty():
    d = should_route_to_executor({})
    assert isinstance(d, HookDecision)
    assert d.route is False


def test_does_not_route_a_single_small_edit():
    # A normal one-file edit must never be hijacked.
    d = should_route_to_executor({
        "tool": "Edit",
        "files": ["src/app.py"],
        "description": "fix a typo in the header",
    })
    assert d.route is False


def test_routes_only_when_explicitly_flagged_large_build():
    # Conservative trigger: an explicit marker the orchestrator/user sets.
    d = should_route_to_executor({
        "cld_large_build": True,
        "plan_path": "plan.md",
    })
    assert d.route is True
    assert "plan.md" in d.reason


def test_does_not_route_without_plan_even_if_flagged():
    # Routing to the executor requires a plan to dispatch; no plan -> no route.
    d = should_route_to_executor({"cld_large_build": True})
    assert d.route is False


def test_many_files_alone_is_not_enough():
    # Touching several files is NOT sufficient on its own — too easy to misfire.
    # Without the explicit large-build flag + plan, stay hands-off.
    d = should_route_to_executor({
        "tool": "Edit",
        "files": ["a.py", "b.py", "c.py", "d.py", "e.py"],
    })
    assert d.route is False


def test_reason_is_populated_either_way():
    assert should_route_to_executor({}).reason
    assert should_route_to_executor({"cld_large_build": True, "plan_path": "p.md"}).reason
