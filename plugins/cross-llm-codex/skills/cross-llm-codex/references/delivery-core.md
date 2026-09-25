# Delivery core: gates and authorization (shared, host-neutral)

This reference is vendored identically into every host variant of the
cross-llm delivery skill. It fixes the two things that must not drift between
hosts: the driver's gate (exit-code) contract and the authorization rules the
lead agent follows, whichever host orchestrates the build. Host-specific
workflow details live in each host's own references, not here.

## Gate contract (driver exit codes)

Every `python scripts/run_delivery.py` invocation ends at a gate. Prefer
`--json` so the gate and summary are machine-checkable, then act on the exit
code:

- **0** -- the operation succeeded; work remains. Continue with the next step.
- **2** -- execution/test failure or dependency defer; inspect the named
  evidence under `<repo>/.cld/runs/<run-id>/` before retrying anything.
- **3** -- every slice is integrated and verified; review the recorded
  commit/ref. The build is done.
- **4** -- lead repair is required; follow the host's repair loop. Failed
  worktrees are retained for that purpose.
- **5** -- invalid plan/state, missing prerequisite, lock or policy block;
  resolve the named cause first. Do not retry blindly.
- **6** -- accepted commits await integration; integrate before dispatching
  any dependent slice.

Acceptance and integration are separate: an accepted slice is not verified
until `--integrate --integration-tests <selector>` has merged and re-tested
the frozen candidate.

## Authorization guidance (all hosts)

- **The user picks the executor and model.** Present the shortlist once,
  before the first dispatch of a build, and keep that choice for the whole
  build. A default existing is not permission to choose on the user's behalf;
  never silently choose or switch models.
- **Billed work needs existing authorization.** Never claim a provider's cost
  is free. Before dispatching on a metered model (including validation runs on
  one), confirm the spend is covered by the user's existing authorization; ask
  only when that is unclear. Declining falls back to the default with the
  user's agreement.
- **Repairs follow the host's active approval policy.** On gate 4, fix only
  the permitted source files in the retained worktree; keep committed
  acceptance tests and protected inputs unchanged. Repair verification and
  integration never invoke the provider, and never modify the user's checkout.
- **No silent re-dispatch.** Never silently dispatch another paid attempt
  after a failure; surface the evidence and let the user steer.
- **Respect the user's project instructions** (AGENTS.md and friends). Never
  install, overwrite, or replace them, and never claim discovery, capability,
  or submission readiness that has not actually been verified.
