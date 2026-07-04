"""Opt-in enforcement-hook decision logic.

This module is the *advisory* core of an optional PreToolUse hook that can route
large-build implementation to the executor while Claude stays the judge. It is
**opt-in and never auto-installs** — see `skill/hooks/README.md`.

Design principle: **conservatism above cleverness.** A hook that intercepts tool
calls can do real damage if it misfires (hijacking a normal edit, breaking flow).
So the classifier defaults to *not* routing and only routes on an explicit,
unambiguous signal: the caller has marked the work as a large build AND supplied a
plan to dispatch. Heuristics like "touches many files" are deliberately NOT enough
— they're too easy to trigger by accident. When in doubt, stay hands-off.
"""

from dataclasses import dataclass


@dataclass
class HookDecision:
    route: bool
    reason: str


def should_route_to_executor(tool_input: dict) -> HookDecision:
    """Decide whether a tool call should be routed to the cheap executor.

    Returns a HookDecision. Routes ONLY when the input is explicitly flagged as a
    large build (`cld_large_build: True`) AND carries a plan to dispatch
    (`plan_path`). Anything else — a normal edit, several files, a missing plan,
    empty input — is left alone (`route=False`). This guarantees the hook can never
    hijack ordinary work.
    """
    if not tool_input:
        return HookDecision(False, "empty input — not routing (default hands-off)")

    flagged = bool(tool_input.get("cld_large_build"))
    plan_path = tool_input.get("plan_path")

    if flagged and plan_path:
        return HookDecision(
            True, f"explicit large-build flag + plan ({plan_path}) — route to executor"
        )
    if flagged and not plan_path:
        return HookDecision(
            False, "large-build flag set but no plan_path — cannot dispatch, not routing"
        )
    return HookDecision(
        False, "no explicit large-build flag — staying hands-off (conservative default)"
    )
