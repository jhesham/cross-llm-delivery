# Optional enforcement hook (advanced)

This directory contains an **opt-in, advisory** PreToolUse hook that can nudge
large-build implementation toward the cheap executor while Claude stays the judge.

> **It is not installed automatically, and you should not install it unless you
> understand what it does.** It is the "advanced" finishing touch — the product works
> fully without it.

## What it does

`route_to_executor.py` reads each tool-call event and consults
`cld.hook.should_route_to_executor` — a **deliberately conservative** classifier. It
routes (advises dispatching to the executor) **only** when the tool input is
explicitly flagged as a large build *and* carries a plan path:

```json
{ "cld_large_build": true, "plan_path": "plan.md" }
```

For everything else — a normal edit, several files, a missing plan — it does nothing
and passes the tool call through untouched. This is by design: a hook that misfires can
hijack ordinary work, so the default is hands-off. Heuristics like "touches many files"
are intentionally **not** triggers.

The reference script is also **non-destructive**: when it does decide to route, it only
emits an advisory `systemMessage` suggesting `run_delivery.py` — it does not seize the
tool call. Make it actually dispatch only if you want that, and only after testing.

## Why it's safe to install as-is

- Conservative classifier → cannot hijack a normal edit (unit-tested in
  `tests/test_hook.py`).
- Fails open → if `cld` isn't importable or the event can't be parsed, it returns
  `{"continue": true}` and never blocks your tool call.
- Advisory only → suggests, doesn't seize.

## Install (only if you want it)

Add to your Claude Code `settings.json` under `hooks.PreToolUse` (adjust the path):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "python /abs/path/to/skill/hooks/route_to_executor.py" }
        ]
      }
    ]
  }
}
```

To **disable**, remove that block. There is no global state to clean up.

## Customizing the trigger

The trigger logic lives in `cld.hook.should_route_to_executor` (pure, tested). If you
want different routing rules, change it there and the tests will tell you immediately
whether you've made it less conservative than intended.
