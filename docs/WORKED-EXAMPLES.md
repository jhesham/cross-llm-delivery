# Two hosts, one engine

Both examples use a freshly generated bundle from the same source revision
and the explicit OpenCode spec `opencode:opencode/kimi-k3`. That ID was observed
on the recorded Windows CLI; check your installed CLI/account and validation
policy. These are executable instructions, not claims of a new live canary.

## Common one-slice repository

In a disposable Git repo, create `double.py`:

```python
def double(value):
    raise NotImplementedError
```

Create `test_double.py`:

```python
from double import double

def test_positive():
    assert double(2) == 4

def test_negative():
    assert double(-3) == -6
```

And `plan.md`:

```markdown
## SLICE: A
brief: Implement double(value) in double.py for positive and negative integers; make test_double.py pass without editing tests.
files: double.py
acceptance_test_path: test_double.py
deps:
```

Commit the baseline/tests/plan. Run `python -m pytest test_double.py` and confirm
the two tests fail from the unfinished implementation. Replace placeholder
paths below with **absolute** paths; quote paths containing spaces.

## Codex as lead, OpenCode as executor

Install the Codex-host `cross-llm-opencode` bundle, start a fresh Codex CLI/IDE
session and invoke `$cross-llm-opencode`. Codex reviews the committed contract
and drives its own vendored script:

```bash
python "<codex-skill>/scripts/run_delivery.py" "<repo>/plan.md" --repo "<repo>" --host codex --dry-run --json
python "<codex-skill>/scripts/run_delivery.py" "<repo>/plan.md" --repo "<repo>" --host codex --step --workers 1 --executor opencode:opencode/kimi-k3 --validation-policy allow --budget-attempts 2 --json
python "<codex-skill>/scripts/run_delivery.py" "<repo>/plan.md" --repo "<repo>" --host codex --integrate --integration-tests test_double.py --json
```

The live step assumes the user authorized the exact model and two calls:
one needed validation plus one production attempt. Fresh valid evidence can
avoid validation; a failure/timeout may exhaust the allowance. Inspect the
gate rather than automatically raising the budget. Expected acceptance is
gate 6; successful integration is gate 3 with the recorded final ref/SHA.

## Claude Code as lead, the same OpenCode executor

Install the Claude-host `cross-llm-opencode` bundle from the same source commit.
In a fresh Claude Code session ask it to run this plan with that exact model.
Claude uses its bundle's driver, against a separate disposable repo or the
same existing ledger when deliberately resuming:

```bash
python "<claude-skill>/scripts/run_delivery.py" "<repo>/plan.md" --repo "<repo>" --host claude-code --dry-run --json
python "<claude-skill>/scripts/run_delivery.py" "<repo>/plan.md" --repo "<repo>" --host claude-code --step --workers 1 --executor opencode:opencode/kimi-k3 --validation-policy allow --budget-attempts 2 --json
python "<claude-skill>/scripts/run_delivery.py" "<repo>/plan.md" --repo "<repo>" --host claude-code --integrate --integration-tests test_double.py --json
```

The same contract, usage policy and gate meanings apply; changing the lead
does not authorize a new paid attempt. Inspect status with `--status --repo
"<repo>" --json`, and use the [recovery guide](MIGRATION.md) on failure.
Review the integrated ref/SHA and merge it explicitly into the intended clean
branch. The original checkout remains the committed unfinished baseline until
that merge, so running its tests immediately after CLD integration still sees
the original code.

## Optional Codex executor: Luna/max/fast

Use a `cross-llm-codex` bundle for either lead. When the user explicitly selects
Luna/max/fast, change the step executor to `codex:gpt-6-luna@max+fast` and retain
the authorized validation/attempt policy. For a larger slice, explicitly set
`CLD_DISPATCH_TIMEOUT=1200` before invoking the driver (PowerShell:
`$env:CLD_DISPATCH_TIMEOUT = "1200"`; POSIX: `export CLD_DISPATCH_TIMEOUT=1200`).
Restore the previous setting afterward. No automatic deadline/usage increase
or tier removal is allowed. Exposed unsupported-tier warnings fail dispatch;
missing actual-tier telemetry cannot prove delivered fast service.
