# Current handoff

Updated 2026-09-23. T01–T11/M1–M3 and **T12A complete**. T12 parent remains open for T12B.
Stop here for the user's explicit token-availability confirmation before T12B. Branch
`refactor/codex-support`, remote `public`; T12A code/test head `8ef2a38`. No main merge or release.

T12A produced `--host codex` standalone bundles under `dist/codex/` for antigravity, cursor and
opencode. The default Claude output path remains intact. Codex entry skills start with YAML
frontmatter and link workflow/provider references; vendored JSON driver previews run from another
working directory. The nine corrected acceptance cases are red on the original baseline and green
on the feature; 25 focused tests and the local full suite passed. [Windows/Ubuntu CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/35845344191)
passed full tests and default generator smoke. All three Codex bundles built and passed local
standalone checks. See [T12A evidence](T12A-EVIDENCE.md).

Dogfood used exact `opencode/kimi-k3`, no substitution. Validation reported 49,738 tokens and
USD 0.053958. Production timed out at 540 seconds; final usage/cost are unknown, with completed
step lower bounds 879,480 tokens and USD 0.9173688. The lead reviewed/manual-integrated the
retained changes after correcting two lead-owned test assertions. Do not claim the engine accepted
or integrated that timed-out candidate. Ignored `.cld/t12a-dogfood/` retains ledger, controller,
logs and the failed attempt worktree. Leave these artifacts in place.

At the next authorized sitting, write and commit T12B's contract and red acceptance before
dispatch. Scope: optional `agents/openai.yaml`, plugin packaging/metadata, remaining host text
parity, CLI/reproducibility and 2-host × 3-provider offline CI. Use exact Kimi K3 via OpenCode
if dogfooding continues. Preserve default Claude compatibility and do not mark parent T12 complete
until T12B passes. Stop again after T12B and request token availability before T13.
