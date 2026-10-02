# Claude executor (v0.4.0) evidence

## Sitting 1 — lead (2026-10-02)

Commits `2e4f9aa`..`12013e7`: `run_process(unset_env=…)`, the shared native-CLI
launcher (Codex migrated onto it; review finding R07 fixed with a regression
proven red against the old gate), the three new final errors, Claude exact-ID
and effort checks, provider validation extra, and red acceptance tests for three
CLD slices. Full offline suite afterwards: 1108 passed; the 46 failures were the
45 intended red slice tests plus plugin freshness (expected until regeneration).

## Sitting 2 — CLD dogfood (2026-10-02)

- Builder: installed Claude-host `cross-llm-codex` skill (v0.3.1, `a464f77`);
  target: this repository's source; ledger `.cld/v040-ledger.json`.
- Executor `codex:gpt-6-luna@max+fast`, one worker, `CLD_DISPATCH_TIMEOUT=1200`,
  `--validation-policy allow`, `--budget-attempts 7`. Launched detached
  (`Start-Process`), so the lead harness's background limit could not kill it.
- Run `9ddb25c3e2ee474b97b0dbe903fa9100`:

| Dispatch | Kind | Outcome |
|---|---|---|
| 1 | validation | verified (v0.3.1 evidence contract 2 made earlier evidence stale once) |
| 2 | CATALOG | accepted, attempt 1 (`4180ecc`) |
| 3 | CONTRACT | accepted, attempt 1 (`271985f`) |
| 4 | PREFLIGHT | accepted, attempt 1 (`b7d5664`) |

- Usage (provider-reported, complete for all four dispatches): input 1,530,941
  tokens (1,349,888 cache read), output 53,029; USD cost unknown (the Codex CLI
  reports none). Budget used 4 of 7.
- Before integration the lead reviewed each diff against the plan interfaces and
  ran CATALOG's neighbouring existing tests on the accepted commit (green).
- Integration: `--integrate --integration-tests tests/v040` passed (gate 3);
  verified commit `4fd5c66`, fast-forwarded onto `refactor/codex-support`.
- Lead review found one defect inherited from the plan's interface text:
  `parse_result` classified login phrases in a *successful* result's text as
  `not_logged_in`. Fixed red-first (`test_success_text_mentioning_login_is_not_misclassified`).

## Sitting 3 — live isolation probe (2026-10-02)

One `claude-haiku-4-5@low` session (CLI 2.1.286, Pro subscription) in a
throwaway repo, launched with the exact contract argv through the native
`claude.exe` resolved behind the npm shim, prompt on stdin, API-key variables
unset. Model-free preflight beforehand: subscription login, every required flag
present, CLD preflight clean.

- Result: exit 0, one JSON object, `subtype: success`, `is_error: false`,
  `num_turns: 5`, 8.9 s; `hello.txt` created; `python -c "print(1)"` ran.
- `modelUsage` keys: `claude-haiku-4-5` and `claude-haiku-4-5-20251001`
  (exact and dated forms both appear; the contract accepts either).
- Usage reported in full: input 26, output 719, cache read 21,797, cache
  write 11,569; CLI cost estimate USD 0.0300 (recorded as an estimate only).
- `--restricted` did **not** block appending to `pyproject.toml`; the spec's
  assumed configuration-file limit was removed from SPEC and setup notes.
- Isolation: no claude-mem session or prompt referenced the probe, no
  `~/.claude/projects` folder or transcript was created (`--safe-mode`,
  `--no-session-persistence` confirmed).
- The captured result replaced the synthetic `tests/fixtures/claude/success.json`;
  all provider tests pass against it.
