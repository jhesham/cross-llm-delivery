# T17 execution slices

T17 precedes T14 because T14's fresh cross-host flow depends on installable wheel and bundle artifacts. Close one child at a time and stop for the user's token confirmation after each child. Parent T17 remains open until all children and the [T17 gate](06-PACKAGING-RELEASE.md#t17--wheel-bundles-and-ci) pass.

## T17A — Wheel/sdist resources and isolated core

- [x] Commit a red artifact-level regression and bounded Kimi K3/OpenCode contract before dispatch. [Evidence](T17A-EVIDENCE.md).
- [x] Package all six provider Markdown resources in wheel and sdist. Build from a clean copied source and verify installed provider registry plus CLI under `python -I -S` outside the checkout. Lead-owned source fix `ae0556a` after CLD retained the protected `pyproject.toml` candidate.
- [x] Lead review, focused/full offline suite, Windows/Ubuntu CI, artifact filename/hash and usage evidence; commit/push handoff, then pause. [Evidence](T17A-EVIDENCE.md); source fixes `ae0556a`, `e979372`.

## T17B — Bundle matrix and tracked freshness

- [x] Build six host/provider combinations into a fresh output root and validate each isolated entrypoint and metadata, including Codex plugin manifests and catalog. [Evidence](T17B-EVIDENCE.md).
- [x] Diagnose and close the existing tracked Claude-plugin regeneration drift; add a deterministic CI freshness check with intentional banner normalization. Preserve the Claude default and Codex ignored output routes. Red contract `7997ecb`, generated refresh `d09a2ab`.
- [x] Verify, commit/push evidence and handoff, then pause. [Evidence](T17B-EVIDENCE.md).

## T17C — CI matrix and compatibility gate

- [x] Run Python 3.11 and a current supported version on Windows/Ubuntu; state macOS as unverified unless covered. Keep live model calls excluded. Python 3.11/3.14 × Windows/Ubuntu [CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/35972684121).
- [x] Add or consolidate meaningful plan/result/state-schema, installed wheel, bundle freshness and real-Git regressions; resolve any remaining temporary xfails that T17 owns. [Evidence](T17C-EVIDENCE.md).
- [x] Complete R07/A05 and T17 gate with full cross-platform CI, artifact hashes and evidence; commit/push handoff, then pause before T14. [Evidence](T17C-EVIDENCE.md).
