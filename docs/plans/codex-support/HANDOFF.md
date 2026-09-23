# Current handoff

Updated 2026-09-23. T01–T11/M1–M3 complete. **T12A in progress**, authorized for Kimi K3
through OpenCode. T12 was split into two child slices in T12-SLICES.md after T11's costly
long-running dogfood. Stop for the user's token confirmation after T12A before T12B.

Branch `refactor/codex-support`, remote `public`; T11 code/test head `8759ce7`, closing docs
`539d82e`. T11 CI passed Windows 761, Ubuntu 758/3 Windows-only skips and both generator smoke.
T12A contract: T12A-CONTRACT.md; executable plan: T12A-DOGFOOD.md; lead acceptance:
tests/test_t12a_generator.py (9 expected red assertions). Explicit PyYAML dev dependency supports
real YAML validation. Baseline must be committed before Kimi dispatch. T12B owns plugin/agent
metadata and final host parity; parent T12 stays unchecked until T12B passes.

Exact model `opencode/kimi-k3` is listed by OpenCode 1.18.29. Use a project-local evidence store
and normal T09 admission; no model substitution. One production attempt/worker, no automatic retry,
strict allowed paths. T11 production totals remain unknown; its partial lower bounds are retained
in T11-EVIDENCE.md and must not be represented as this new run's spend.

After T12A candidate: independently verify the immutable red baseline and allowlist, integrate
accepted commit, run affected generator tests and full cross-platform CI if shared generator changes,
record usage honestly, close only T12A in tracker, commit/push and stop. No main merge or release.
