# N04 — frozen acceptance import isolation

Implemented 2026-10-03. Runtime source: `6b9cc7cb15b284e8dd0c3518f77b322cff6807de`.
Initial failing regressions: `a3ca85b` (all eight initial cases failed).

## Result

The default CLI judge and validation probe now resolve project imports against
the captured candidate. Registered Git checkout paths in `PYTHONPATH`, legacy
editable paths, modern editable finders and namespace locations are mapped to
the frozen tree. Its root and standard `src` directory take precedence over
installed duplicates. Independent external dependencies remain available.

The trusted stdlib bootstrap replaces editable loaders as well as their origins.
It rejects live project modules already loaded at Python startup or detected
after testing. An engine-owned stdin policy avoids Windows command-line limits
for large checkout inventories. Candidate scope is thread-local and also covers
the existing repair and integration judging paths.

## Verification

- Initial red commit: eight real-Git regressions failed before implementation.
- Final-source regression recheck: **20 passed in 116.24 s**. Covers both judge
  and validation, false approval/rejection, editable/installed imports, namespace
  imports, startup/late-loader rejection and a large checkout inventory.
- Broader acceptance, validation, candidate, repair, integration, CLI contract and
  Windows group: **201 passed in 611.29 s**. A final canonical-path comparison
  refinement was then covered by the 20-case recheck; counts overlap and should
  not be added together.
- Packaging, both-host bundles and parity tests: **18 passed in 39.00 s**.
- Regenerated five providers for both hosts from the committed runtime above;
  all ten standalone bundles match **40 core Python files** byte-for-byte.
  Claude plugin freshness passed for all five tracked packages. Portable Codex
  plugins and their five-provider marketplace were also regenerated.
- Outside-checkout smoke: the generated Codex-host/Codex-provider bundle rejected
  a broken frozen candidate and accepted a correct one while live source
  disagreed in each direction. This exercised the real subprocess bootstrap.
- Cross-platform CI: pending push/run identification at this checkpoint.

## Boundaries and restart

This is import isolation, not an operating-system sandbox. External dependencies
and explicitly injected custom test runners remain trusted inputs. Existing
accepted/integrated ledger records are not retroactively re-judged; use a fresh
build if earlier acceptance relied on live source outside its snapshot.

No executor inference, global installation, release promotion or publication was
performed. Executor tokens: **0**; lead token usage is unavailable. N05–N08 remain
pending, explicitly authorized through CLD with `codex:gpt-6-luna@max+fast`.
Confirm N04 CI is green and user token availability before starting N05.
