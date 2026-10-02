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

## Sitting 3 — validation and first delivery (2026-10-02)

Source driver, throwaway repo with one red slice (`add` in `calc.py`),
`--executor claude:claude-sonnet-5@low --validation-policy allow --budget-attempts 3`,
launched detached. Run `f861dbf727b04b6690929a43b8efeb76`:

| Dispatch | Kind | Outcome | Tokens (input+output) | CLI estimate |
|---|---|---|---|---|
| 1 | validation | verified | 313 | USD 0.0686 |
| 2 | slice ADD | accepted, attempt 1 | 358 | USD 0.0221 |

- Usage complete for both dispatches: input 12, output 659, cache read 70,566,
  cache write 16,918; CLD cost unknown by design (estimates kept as raw usage).
- `--integrate --integration-tests tests/test_calc.py`: gate 3, verified commit
  `6624c51` (`refs/cld/integration/f861dbf…/0a9c89a…`).
- Validation evidence stored for `claude:claude-sonnet-5@low` (status `verified`,
  context contract 2 with the subscription account identity).

## Sitting 3 — Codex-lead canary (2026-10-02)

Codex-host `cross-llm-claude` bundle (built from `85d9aea`) installed with
`generator/install_codex.py` into a throwaway repo's `.agents/skills`; lead
`codex exec --model gpt-6.1-sol -c model_reasoning_effort="high"`, launched
detached, instructed to follow the skill's driver sequence with
`--executor claude:claude-sonnet-5@low --validation-policy allow --budget-attempts 5`.
The lead ran with `--sandbox danger-full-access`: non-interactive `codex exec`
cannot request escalation, and CLD must write outside the repo (validation
evidence, process temp, Claude config). A sandboxed lead with explicit
writable roots remains unverified.

**First run (stopped correctly at gate 4).** Preview 0 → step A 6 → integrate 4.
The canary prompt used `--integration-tests tests`, which includes slice B's
still-red test; integration correctly refused ("baseline failure persists").
The lead stopped as instructed and reported accurately. Claude usage: one
validation probe (evidence is keyed per repository) and slice A, ~700 tokens +
~98K cache, CLI estimate ~USD 0.046. Codex lead: input 384,044 (361,344 cached),
output 1,972.

**Re-run (`--new-build`, selector `tests/test_names.py`), run
`a878967f79be49c0af99a50075c60c52`.** Lead gates: preview 0 → step A 6 →
integrate A 0 → step B 6 → integrate B 3. Both slices accepted by the Claude
executor on attempt 1; validation evidence reused (no probe). Verified
independently: ledger both `integrated`; integration ref
`refs/cld/integration/a878967f…/9f786e69…` = `c0ccbdf`; at that commit both
acceptance tests pass with correct implementations.

| Party | Usage |
|---|---|
| Claude executor (2 dispatches) | 1,049 tokens; cache read 114,623, cache write 5,272; CLI estimate USD 0.0567 |
| Codex lead (gpt-6.1-sol, high) | input 316,160 (292,608 cached), output 1,793 |

**Lessons for documentation:** (1) a layered plan's integration selector must
stay green after every layer — select already-satisfiable or earlier-layer
tests, never later slices' red tests; (2) on Windows the Codex lead runs the
driver through `pwsh -Command`, whose process exit is 1 for any non-zero native
exit, so leads must act on the JSON `gate_code`, not the shell exit code.
