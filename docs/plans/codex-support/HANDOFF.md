# Current handoff

Updated 2026-09-18. T01–T08, M1/M2 complete. **T09 verification in progress.**
User authorized T09; do not advance to T10. Read T09-CONTRACT.md and T09-EVIDENCE.md.

Implemented consistent model/context admission, explicit noninteractive validation spend policy,
trusted isolated validation probes, atomic synchronized evidence, and selected-provider/filesystem
preflight. Focused checks pass. Full local offline suite and Windows/Ubuntu CI must pass before
closing T09. Source files only; generated plugins refresh in T12/T17.

Commit/push T09 to public/refactor/codex-support, update evidence/checklists, then pause for the
user's token checkpoint. No release/merge. No live provider calls or sub-agents; executor usage
zero; lead counters unavailable. Kimi K3 via OpenCode remains the later dogfood choice, exact
model ID must be verified before first dispatch. No silent substitution.

T10 next: cumulative persisted usage, model/cost provenance and budget reservations including
validation, retries and escalation; phase 3 contains the checklist. Estimated lead allowance 8–12k.
