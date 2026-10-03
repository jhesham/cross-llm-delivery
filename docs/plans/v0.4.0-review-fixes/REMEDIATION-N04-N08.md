# N04–N08 implementation checkpoints

Authorized 2026-10-03. Work one committed slice at a time; stop after each slice
for the user's token-availability check. N04 is implemented directly by Codex.
N05–N08 use CLD with **`codex:gpt-6-luna@max+fast`**, as explicitly selected by
the user. Do not substitute a model, effort, or tier; an unsupported fast tier
must stop dispatch rather than silently using standard service.

| Slice | Scope | Method | Status |
|---|---|---|---|
| N04 | Frozen candidate project imports | Direct implementation and real-Git regressions | Locally verified; CI pending |
| N05 | Codex configuration identity | CLD / exact Luna max + fast | Pending |
| N06 | Five-provider recursion contract | CLD / exact Luna max + fast | Pending |
| N07 | Native Windows OpenCode discovery | CLD / exact Luna max + fast | Pending |
| N08 | Antigravity native POSIX cwd | CLD / exact Luna max + fast | Pending |

Detailed requirements and corrective checklists:
[full review](FULL-REVIEW-2026-10-03.md).

## N04 closure

- [x] Commit failing real-Git import regressions before implementation (`a3ca85b`;
      all eight initial cases failed).
- [x] Cover false approval and false rejection through inherited `PYTHONPATH`,
      legacy editable paths, modern editable finders and installed-package shadowing.
- [x] Preserve independent dependencies and cover namespace-package locations.
- [x] Block live project modules imported at startup or by a late finder.
- [x] Use the same policy for the CLI acceptance runner and model validation,
      under the candidate scope also used by repair/integration.
- [x] Send checkout inventory through stdin to avoid Windows argv limits.
- [x] Finish final focused checks and record counts against final source.
- [x] Commit runtime changes, then generate both hosts' five bundles/plugins
      from that committed runtime source.
- [x] Verify artifact parity, standalone operation and packaging.
- [ ] Push the working branch and record exact-source CI status.
- [ ] Update handoff and stop for token availability before N05.

## Each CLD slice (N05–N08)

- [ ] Confirm N04's independent gate and cross-platform CI are green before
      relying on CLD for the next implementation.
- [ ] Commit scoped failing acceptance tests and a precise file allowlist/contract.
- [ ] Use the current generated Codex-provider driver containing N04, with a
      separate bound ledger/plan and preserved worktree/evidence.
- [ ] Pin `codex:gpt-6-luna@max+fast`; verify local CLI capability/account setup.
      Protect Codex config identity explicitly with `--validation-config` while
      N05's automatic discovery remains unfixed.
- [ ] Permit a bounded validation canary only if current exact-spec evidence is
      absent. Set explicit token/attempt caps and record unknown cost honestly.
- [ ] Run one implementation dispatch; inspect failures before any further spend.
      Do not silently retry with another model/tier or escalate.
- [ ] Review the candidate, independently run acceptance/adjacent tests, integrate
      through the checked CLD gate, and bring only the reviewed commit into the
      working branch.
- [ ] Regenerate affected artifacts from committed source; update checklist,
      handoff and measured executor usage; stop at the slice checkpoint.

No live executor calls or global installs are part of the N04 checkpoint.
Existing ledgers are not retroactively re-judged by the import fix. Start a fresh
build if earlier acceptance relied on source outside its frozen candidate.

N04 verification and runtime provenance:
[import isolation evidence](N04-IMPORT-ISOLATION-FIX.md).
