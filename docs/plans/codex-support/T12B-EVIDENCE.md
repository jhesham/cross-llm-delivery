# T12B dogfood evidence — host metadata and parity

2026-09-23. The user authorized T12B after the T12A checkpoint. The pinned executor was exactly
`opencode:opencode/kimi-k3`; there was one validation probe and one production attempt, with no
fallback, subagent or automatic retry. The lead committed the contract, executable plan and 11
red acceptance cases before dispatch (`65b0ee4`, assertion-only correction `0884a03`, parseable
plan `693a9e7`). A clean detached-worktree `CandidateVerifier.preflight` accepted the committed
red baseline and protected inputs (fingerprint
`7dee67b40d0831bdb06edd3e142381d5036dce8b81af86175471a38bea09ab4c`).

The isolated project-local evidence/ledger/controller are under `.cld/t12b-dogfood/`; no
machine-wide evidence was changed. Run ID `8bd3677c9fc84463abae432804f02359`. Trusted model
validation reported **50,375 tokens, USD 0.052737** (input 10,750, output 535, cache read
39,040). Production reported **1,744,000 tokens, USD 1.0429632** (input 63,624, output 12,283,
cache read 1,656,704). Combined ledger total: **1,794,375 tokens, USD 1.0957002**; all usage
categories are known. The production attempt exceeded its 1,500,000-token admission reservation,
which was a policy allowance, not an enforced provider cap. Cumulative use remained under the
1,800,000-token allowance. There was no second paid production attempt.

The engine accepted only the seven allowed source paths, with the lead tests/contract protected,
as collected commit `3553732b3d7a27068f14ed06dc61d3dece62775c`. An independent integration
gate re-ran the committed T12B suite from the baseline and frozen candidate, then published
integration commit `892bcc0c18beaad64548da0066436a1343819fbc`; journal:
`.cld/runs/8bd3677c9fc84463abae432804f02359/integration/5d136a5f0b654200995609875de040e6`.
The accepted change was cherry-picked to `refactor/codex-support` as `aeea9ce`.

Lead review found that a bare Codex plugin-generation command defaulted to the tracked Claude
`plugins/` tree. A new regression failed first; the lead changed only Codex's default output to
ignored `dist/plugins/` while keeping no-argument Claude packaging in `plugins/`. The no-argument
Claude plugin layout, names and repeated bytes were checked in an isolated root. Review fix:
`d7b591e`.

The resulting six host/provider bundles run the vendored JSON preview outside the checkout with
empty PYTHONPATH. Codex bundles contain [officially documented](https://developers.openai.com/plugins/deploy/submission-errors)
`agents/openai.yaml` fields and a shared host-neutral reference. Codex plugin packages use the
[portable root manifest and skills layout](https://developers.openai.com/plugins/build/plugins)
in disposable output. Claude generated instructions now point at their vendored driver and no
longer require a source checkout install. These are generation checks; actual Codex discovery and
installation remain T13.

The focused T12B/T12A/existing-generator suite passed **38 cases**, and local default/Codex skill
build plus Codex plugin packaging smoke passed. The first full CI at `d7b591e`
([run 35849332769](https://github.com/jhesham/cross-llm-delivery/actions/runs/35849332769))
failed on Ubuntu in the pre-existing process-recovery test. Its fixed 0.6-second cancellation timer
raced grandchild startup, leaving an empty file before the intended partial edit. The lead changed
the fixture to signal cancellation after observing that edit, with a bounded timeout; the focused
recovery file passed locally (four cases). Fix: `3b1c0b9`. The local full offline suite also
passed; it started before the timing-fixture edit, so the focused recovery run and final CI
cover that final change. Final
[Windows/Ubuntu CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/35849789785)
passed on `3b1c0b9`: both full test jobs, default Claude generator smoke, Codex generator smoke,
and Codex plugin-packaging smoke succeeded. The Windows job took longer but completed successfully.
No live executor calls were made by CI. Lead token usage: unavailable. T12B and parent T12 are
complete; stop for the user's token confirmation before T13.
