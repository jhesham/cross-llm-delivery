# T12 split: host-aware skill generation

The user authorized T12 with Kimi K3 via OpenCode on 2026-09-23. T11 showed that a broad CLI
rewrite incurred long OpenCode sessions and unbounded cached-token growth. T12 is divided into
independently checked child slices, with a mandatory user token checkpoint after each.

- [x] **T12A — Standalone Codex generator.** Add `--host codex|claude-code` to the generator, keep
  the current Claude default byte-for-byte compatible, generate Codex bundles under `dist/codex/`,
  put valid YAML metadata first, supply concise Codex workflow/provider references, and prove
  vendored driver isolation for all three providers. Allowed implementation is deliberately small.
  Contract: [T12A-CONTRACT.md](T12A-CONTRACT.md). Acceptance: `tests/test_t12a_generator.py`.
  [Evidence](T12A-EVIDENCE.md), code/test `8ef2a38`, cross-platform CI passed. Executor production
  usage remains unknown after timeout; observed lower bounds are in evidence. Stop after this slice.
- [x] **T12B — Host metadata and parity.** Add optional verified `agents/openai.yaml` metadata and
  Codex host packaging in generator/build_plugins.py as appropriate; extract shared instruction
  references without changing existing Claude behavior, resolve remaining bundle path/setup text,
  validate the complete two-host × three-provider matrix, CLI/reproducibility and offline CI. Its
  contract and acceptance tests must be committed before any dispatch. Estimated lead effort
  5–8k, plus independent CI. Stop after this child slice. T12 parent closes only then.
  Contract: [T12B-CONTRACT.md](T12B-CONTRACT.md); executable plan:
  [T12B-DOGFOOD.md](T12B-DOGFOOD.md); lead acceptance: `tests/test_t12b_parity.py`
  (11 red assertions before implementation). [Evidence](T12B-EVIDENCE.md), final code/test
  `3b1c0b9`, Windows/Ubuntu CI green. Parent T12 closes here; stop before T13.

T13 owns installation/discovery; T17 owns wheel packaging. T12 checks generated files in disposable
roots, not a user-global install. Existing Claude plugin IDs and default build commands must persist.
Exact dogfood model: `opencode/kimi-k3`. No alternate model or automatic escalation. The T11
production usage unknowns remain historical; they are not zeroed or carried as this run's spend.

Official OpenAI documentation checked 2026-09-23: skill frontmatter starts with YAML `name` and
`description`, while detailed guidance belongs in references/scripts:
https://developers.openai.com/plugins/build/skills . Plugin validation explicitly rejects
frontmatter that does not start at byte zero:
https://developers.openai.com/plugins/deploy/submission-errors . Actual standalone discovery is
reserved for T13/T14 and is not claimed from these generation checks.
