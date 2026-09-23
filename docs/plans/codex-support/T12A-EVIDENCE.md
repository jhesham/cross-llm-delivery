# T12A dogfood evidence — standalone Codex generator

2026-09-23. T12A is the first child of T12; T12B and the parent remain open. The user authorized
Kimi K3 through OpenCode. The exact pinned model was `opencode/kimi-k3` (OpenCode 1.18.29).
One production attempt ran in an isolated delivery worktree, with no fallback or automatic retry.
The lead-owned contract, nine red acceptance cases and PyYAML dev dependency were committed in
`66ea6fe` before dispatch. A clean detached worktree passed the candidate preflight.

Project-local validation evidence, ledger and controller are retained under `.cld/t12a-dogfood/`;
the machine-wide evidence store was not changed. Run ID:
`cd607552fcfa427487e9783bc5a3a688`. The trusted validation probe passed: 49,738
provider-reported tokens (input 10,636, output 551, cache read 38,400), USD 0.053958.
Production ran with a 540-second timeout, one worker, no retries and a 1,000,000-token/USD 2
per-attempt admission reservation. These reservations are not hard provider caps. It timed out,
so normalized production usage and final cost are **unknown**. The 22 completed OpenCode step
records contain at least 879,480 reported tokens and USD 0.9173688, partial lower bounds only.
Validation plus observed production is at least 929,218 tokens and USD 0.9713268; it is not a
complete bill. No second billed production attempt was dispatched.

The timeout left changes only in the three allowed files in the retained worktree:
`generator/build_skill.py`, `skill/hosts/codex/SKILL.template.md`, and
`skill/hosts/codex/references/codex-workflow.md`. The delivery ledger recorded `needs_repair`,
not accepted or integrated. The lead independently inspected and copied those changes into the
branch, corrected two lead-owned acceptance assertions (path-dependent generated `.pyc` files
and an erroneous directory-name substring check), and clarified bundle-relative command paths
and already-granted user authorization in the Codex instructions. The protected baseline in a
detached worktree still produced nine red cases with the corrected tests. Because the lead-owned
tests changed after the original delivery attempt, this is a reviewed/manual integration, **not**
a claimed engine verified-repair or collection gate. Code and corrected tests: `8ef2a38`.

The default Claude build path and template remain intact. `--host codex` writes three isolated
bundles under `dist/codex/`, with YAML-first metadata, linked Codex/provider references and the
vendored JSON driver. Unknown hosts fail before output mutation. The Codex entry skill was checked
against the [official skill format](https://developers.openai.com/plugins/build/skills) and
[frontmatter validation rule](https://developers.openai.com/plugins/deploy/submission-errors).
Actual Codex installation/discovery is reserved for T13.

Focused T12A plus existing generator tests: 25 passed. The local full offline suite passed.
Both local generator variants built all three providers: default Claude output and `--host codex`.
The full [CI run](https://github.com/jhesham/cross-llm-delivery/actions/runs/35845344191)
passed on Ubuntu and Windows at `8ef2a38`; each job completed its full test step and default
Claude generator smoke. Codex generation was checked locally for all three providers and in the
focused acceptance matrix. CI coverage of `--host codex` remains in T12B's parity scope.

Final validation: **passed**. Code/test head: `8ef2a38`.
Lead token usage: unavailable. Next task after the user's token checkpoint: T12B.
