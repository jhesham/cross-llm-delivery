#!/usr/bin/env python
"""Reference PreToolUse hook — OPT-IN, advisory.

This is a *reference implementation*. It is NOT installed automatically. Install it
yourself only if you want large-build tool calls routed to the cheap executor (see
README.md in this directory).

Contract: a PreToolUse hook reads a JSON event on stdin and may emit JSON on stdout
to influence the tool call. This script uses `cld.hook.should_route_to_executor` —
a deliberately conservative classifier that routes ONLY on an explicit large-build
flag plus a plan path, and otherwise does nothing (passes the call through untouched).

Because the classifier defaults to hands-off, installing this hook is low-risk: it
cannot hijack a normal edit. It only acts when you've explicitly marked the work.
"""

import json
import sys

try:
    from cld.hook import should_route_to_executor
except ImportError:
    # If cld isn't importable, do nothing — never block the user's tool call.
    print(json.dumps({"continue": True}))
    sys.exit(0)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        print(json.dumps({"continue": True}))
        return 0

    tool_input = event.get("tool_input", {}) or {}
    decision = should_route_to_executor(tool_input)

    if decision.route:
        # Advisory: surface the recommendation. A real installation would invoke
        # skill/scripts/run_delivery.py with the plan here; we keep the reference
        # non-destructive and just annotate, so this script is safe to install as-is.
        print(json.dumps({
            "continue": True,
            "systemMessage": f"[cld] {decision.reason}. "
                             f"Consider: python skill/scripts/run_delivery.py "
                             f"{tool_input.get('plan_path')}",
        }))
    else:
        print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
