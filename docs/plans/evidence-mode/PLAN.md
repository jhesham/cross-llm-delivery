# CLD v0.5 Evidence Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add evidence tasks to CLD:
- investigate, query and materialise tasks, in ask mode and plan mode;
- environments with a fail-closed SQL runner;
- a knowledge-base starter template;
- the superpowers → CLD plan guide.

**Architecture:**
- A new package, `engine/cld/evidence_mode/`, holds environments, the SQL classifier and runner, approvals, the evidence bundle, ask mode and the knowledge-base template.
- Codex gains an evidence invocation with full access.
- The plan parser and orchestrator route evidence slices.
- Code-change slices keep every existing guarantee.

**Tech Stack:** Python 3.11+, stdlib only, pytest. Executors are the existing provider CLIs; Codex first.

**Spec:** [SPEC.md](SPEC.md)

## Global Constraints

- **Stack and platforms:**
  - stdlib Python, 3.11+, Windows and POSIX;
  - existing code-change behaviour, tests and guarantees unchanged;
  - the full offline suite stays green.
- **Trust and safety:**
  - CLD never judges analytical correctness; it checks completeness and enforces the safety boundary only;
  - writes to a `real` environment never happen without a recorded approval, and unclassifiable SQL counts as a write (fail closed);
  - CLD never reads, stores or logs credentials; redact secret-looking values from stderr kept in evidence.
- **Storage:** result data lives in artefacts under `.cld/runs/`, never in the ledger.
- **Executor permissions:** evidence tasks run Codex with `--sandbox danger-full-access`; code slices keep `workspace-write` or `read-only`.
- **Unsupported providers:** a provider without evidence support returns a clean "not supported" block before dispatch.
- **Privacy:** no personal, employer or work-specific names, paths or examples in any file or commit message. Use neutral examples (`warehouse_sandbox`, `orders`, `example-org/service-a`).
- **CLD slices:**
  - acceptance tests fail at baseline by AssertionError only, using lazy-resolve helpers;
  - executor `codex:gpt-6-luna@max+fast`;
  - the lead writes and commits the failing tests, and integrates after each layer.
- **Commits:** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Push, sync and release only on the user's go-ahead.

## Review Focus

1. **Comment or CTE before a write:** SQL beginning with comments or `WITH … AS (…)` then `INSERT`/`MERGE`/`CREATE` must classify as a write. Task 3 `test_cte_then_insert_is_write`.
2. **Missing platform CLI:** when the environment's command (for example `bq`) is not installed, the runner returns `failed` with a clear message and never a result. Task 5 `test_missing_command_fails_clearly`.
3. **Untraced SQL:** an executor reporting SQL it never ran through the runner yields `runner_used: false` and an `incomplete` status, unless the environment is MCP-only. Task 6 `test_sql_not_in_runner_records_is_flagged`.
4. **Huge results:** a 100,000-row result returns a preview capped at 50 rows / 16 KiB plus the artefact path, without loading everything into the lead's response. Task 8 `test_large_result_preview_is_capped`.
5. **Secrets in errors:** connection strings and tokens in stderr are redacted in stored evidence. Task 5 `test_stderr_secrets_redacted`.

---

## Sitting 1 — plan-conversion guide (lead, docs only)

### Task 1: Superpowers → CLD plan guide

**Files:**
- Create: `skill/references/superpowers-to-cld.md`
- Modify: `skill/SKILL.template.md`, `skill/hosts/codex/SKILL.template.md` (one line each pointing to the guide)
- Test: `tests/test_superpowers_guide.py`

**Delivery:** lead.

- [ ] **Step 1: Write the failing test.**
  - `test_guide_ships_in_every_bundle`: after `build_one`, each provider bundle contains `references/superpowers-to-cld.md`.
  - `test_guide_mapping_table`: the guide contains the rows `acceptance_test_path`, `files`, `deps`, `complexity`, and the heading "A task with no test".
  - `test_skills_link_guide`: both SKILL templates mention `superpowers-to-cld.md`.
- [ ] **Step 2: Run the test and confirm it fails.** `python -m pytest tests/test_superpowers_guide.py -q` → FAIL (file missing).
- [ ] **Step 3: Write the guide.** Content per SPEC §9:
  - the mapping table;
  - choosing an integration selector per layer;
  - splitting and merging tasks;
  - the red-baseline rule;
  - one neutral end-to-end example (a lead plans with superpowers, then builds with `codex:gpt-6-luna@max+fast`);
  - a short "evidence slices" section added in Task 14.
- [ ] **Step 4: Regenerate and test.** Regenerate bundles and plugins (both hosts), then run the test → PASS, and `check_plugins_fresh.py` passes.
- [ ] **Step 5: Commit** `docs: superpowers-to-CLD plan conversion guide`.

---

## Sitting 2 — environments, classifier, approvals (CLD slices)

### Task 2: Environment file

**Files:**
- Create: `engine/cld/evidence_mode/__init__.py`, `engine/cld/evidence_mode/environments.py`
- Test: `tests/evidence/test_environments.py`

**Interfaces:**
- **Produces:**
  - `@dataclass(frozen=True) Environment(name: str, cls: Literal["sandbox","real"], platform: str, command: tuple[str, ...], read_only_expected: bool, mcp_only: bool = False, job_id_pattern: str | None = None)`
  - `load_environments(repo: str | Path, path: str | None = None) -> dict[str, Environment]`, reading `<repo>/cld-environments.json` by default
  - `class EnvironmentError(ValueError)`
- **File format:** `{"environments": [{"name","class","platform","command":[...],"read_only_expected":bool, "mcp_only":bool?, "job_id_pattern":str?}]}`. `command` receives the SQL on stdin.

- [ ] **Step 1: Write the failing tests.**
  - `test_loads_sandbox_and_real`: two entries; `cls`, `command` and `read_only_expected` round-trip.
  - `test_rejects_unknown_class`, `test_rejects_duplicate_name`, `test_rejects_empty_command_unless_mcp_only`: each raises `EnvironmentError` naming the field.
  - `test_real_must_declare_read_only_expected`: a `real` environment without `read_only_expected: true` → `EnvironmentError("…read_only_expected…")` (layer 1 is mandatory for real environments).
  - `test_missing_file_is_empty_dict`.
- [ ] **Step 2: Confirm they fail.** Run them; failure must be by AssertionError (lazy-resolve).
- [ ] **Step 3: Dispatch the slice** with executor `codex:gpt-6-luna@max+fast`, `files: engine/cld/evidence_mode/__init__.py, engine/cld/evidence_mode/environments.py`. Lead integrates.
- [ ] **Step 4: Confirm they pass.** The tests pass, and so does the full `tests/evidence` directory.

### Task 3: SQL classifier and statement hash

**Files:**
- Create: `engine/cld/evidence_mode/sqlclass.py`
- Test: `tests/evidence/test_sqlclass.py`

**Interfaces:**
- **Produces:**
  - `classify_sql(sql: str) -> Literal["read","write"]`
  - `statement_hash(sql: str) -> str`: SHA-256 of the SQL with comments stripped and whitespace collapsed.
- **Rule** (fail closed):
  - strip comments; split statements on `;` outside quotes;
  - every statement must start with `SELECT`, `WITH` (with no data-modifying keyword anywhere), `SHOW`, `DESCRIBE`/`DESC` or `EXPLAIN`, otherwise the result is `write`;
  - empty, unparseable or unbalanced quotes → `write`.

- [ ] **Step 1: Write the failing tests.**
  - `test_select_is_read`, `test_leading_comments_select_is_read`, `test_multi_select_is_read`.
  - `test_cte_then_insert_is_write` (Review Focus 1): `"-- note\nWITH a AS (SELECT 1) INSERT INTO t SELECT * FROM a"` → write.
  - `test_create_table_as_select_is_write`, `test_merge_delete_update_drop_alter_truncate_are_write`, `test_declare_script_is_write`, `test_select_then_insert_is_write`.
  - `test_unbalanced_quote_is_write`, `test_empty_is_write`.
  - `test_keyword_inside_string_literal_does_not_flip_select`: `SELECT 'insert' AS x` → read.
  - `test_hash_ignores_comments_and_whitespace`.
- [ ] **Step 2: Confirm they fail.**
- [ ] **Step 3: Dispatch the slice.** `files: engine/cld/evidence_mode/sqlclass.py`.
- [ ] **Step 4: Confirm they pass.**

### Task 4: Approvals store

**Files:**
- Create: `engine/cld/evidence_mode/approvals.py`
- Test: `tests/evidence/test_approvals.py`

**Interfaces:**
- **Produces:**
  - `record_approval(repo, *, env: str, sql_hash: str, approved_by: str, reason: str) -> dict`: appends JSON lines to `<repo>/.cld/approvals.jsonl` under the existing file lock pattern (`cld.locking`);
  - `is_approved(repo, *, env: str, sql_hash: str) -> bool`.

- [ ] **Step 1: Write the failing tests.**
  - `test_approval_round_trip`.
  - `test_approval_is_env_and_hash_specific`: approving env A does not approve env B, and a different hash is not approved.
  - `test_reason_and_approver_required`.
  - `test_corrupt_line_fails_closed`: a malformed line → `is_approved` is False.
- [ ] **Step 2: Confirm they fail.** Then **Step 3: dispatch the slice.** Then **Step 4: confirm they pass.**

---

## Sitting 3 — SQL runner, evidence bundle, Codex evidence mode, ask-mode query

### Task 5: SQL runner and the `--sql` CLI

**Files:**
- Create: `engine/cld/evidence_mode/sqlrun.py`
- Modify: `engine/cld/cli.py`, adding flags `--sql FILE`, `--env NAME` and `--out DIR`, and routing before plan loading.
- Test: `tests/evidence/test_sqlrun.py`

**Interfaces:**
- **Consumes:**
  - Task 2 `Environment`, `load_environments`;
  - Task 3 `classify_sql`, `statement_hash`;
  - Task 4 `is_approved`;
  - `cld.process.run_process`.
- **Produces:**
  - `run_sql(repo, env: Environment, sql: str, *, out_dir: Path, runner=run_process) -> dict`. The returned record has keys `{sql, sql_hash, env, classification, status, rows, duration_s, exit_code, job_id, result_path, sql_path, stderr_tail}`, where `status` is one of `ok`, `needs_approval`, `failed` or `refused`.
  - The record is also written to `out_dir/runs/<n>.json`, with the SQL at `out_dir/sql/<n>.sql` and stdout at `out_dir/results/<n>.out`.
- **Rules:**
  - A write on `real` without approval → `needs_approval`, nothing executed.
  - An MCP-only environment → `refused`, with the message "execute through MCP; layer 1 applies".
  - `rows` is the line count of CSV or the JSON array length when parseable, otherwise `null`.
  - `job_id` comes from `job_id_pattern` applied to stderr and stdout.
  - Redact `(?i)(password|passwd|pwd|token|secret|api[_-]?key|authorization)\s*[=:]\s*\S+` and URL credentials (`//user:pass@`) in `stderr_tail` (last 4 KiB).
- **CLI:** `--sql FILE --env NAME [--out DIR] --json` prints the record as JSON. Exit codes:
  - 0: `ok`;
  - 5: `needs_approval`, `refused` or `failed`.

- [ ] **Step 1: Write the failing tests,** using a fake `runner`.
  - `test_read_on_real_runs_and_records`.
  - `test_write_on_real_needs_approval_and_does_not_execute`: the runner is never called.
  - `test_write_on_real_with_approval_runs`.
  - `test_write_on_sandbox_runs`.
  - `test_missing_command_fails_clearly` (Review Focus 2): the runner raises FileNotFoundError → `status == "failed"` and the message names the command.
  - `test_stderr_secrets_redacted` (Review Focus 5): stderr `"jdbc:pg://u:p4ss@h password=abc token: xyz"` → the stored tail contains none of `p4ss`, `abc`, `xyz`.
  - `test_mcp_only_env_refused`.
  - `test_cli_sql_json_and_exit_codes`.
- [ ] **Step 2: Confirm they fail.** Then **Step 3: dispatch the slice** (`files: engine/cld/evidence_mode/sqlrun.py, engine/cld/cli.py`). Then **Step 4: confirm they pass** and run `tests/test_cli*` to check no regressions.

### Task 6: Evidence bundle and completeness

**Files:**
- Create: `engine/cld/evidence_mode/bundle.py`
- Test: `tests/evidence/test_bundle.py`

**Interfaces:**
- **Bundle file:** the executor writes `evidence.json`:
  - `{task_id, kind, env:[...], notes, sql_runs:[{sql_path, result_path}], findings_path?, created_objects?:[{name, rows, schema}], errors:[...]}`
- **Produces:**
  - `load_bundle(evidence_dir: Path) -> dict`: a missing or invalid file → `{"_invalid": reason}`.
  - `check_bundle(bundle: dict, *, kind: str, evidence_dir: Path, environments: dict[str, Environment]) -> tuple[str, list[str], bool]`, returning `(status, problems, runner_used)`. `status` is one of `complete`, `incomplete` or `needs_approval`.
- **Rules:**
  - Required per kind:
    - query: at least one `sql_runs` entry;
    - materialise: `sql_runs` and `created_objects`;
    - investigate: `findings_path`, which must exist.
  - Each SQL run must match a runner record in `evidence_dir/runs/*.json` by `statement_hash`. An unmatched run sets `runner_used=False` and adds a problem, unless every environment of the task is `mcp_only`.
  - Any runner record with `needs_approval` → bundle status `needs_approval`.
  - A missing `notes` key is a problem; an empty string is allowed.

- [ ] **Step 1: Write the failing tests.**
  - `test_complete_query_bundle`, `test_missing_bundle_is_incomplete`, `test_query_without_runs_is_incomplete`, `test_materialise_requires_created_objects`, `test_investigate_requires_existing_findings`.
  - `test_sql_not_in_runner_records_is_flagged` (Review Focus 3).
  - `test_mcp_only_env_does_not_require_runner`.
  - `test_needs_approval_propagates`.
- [ ] **Step 2: Confirm they fail.** Then **Step 3: dispatch the slice.** Then **Step 4: confirm they pass.**

### Task 7: Codex evidence invocation and the provider capability flag

**Files:**
- Modify:
  - `engine/cld/providers_api.py`: `Provider.supports_evidence: bool = False`;
  - `engine/cld_providers/codex/contract.py`: `build_invocation(..., evidence: bool = False)`;
  - `engine/cld_providers/codex/provider.py`: `CodexExecutor(..., evidence: bool = False)` passes it through, and `PROVIDER.supports_evidence = True`.
- Test: `tests/evidence/test_codex_evidence.py`

**Interfaces:**
- **Rules:**
  - With `evidence=True`, the invocation uses `--sandbox danger-full-access` and an evidence role prompt. The prompt says:
    - you are an evidence executor;
    - run all SQL with the given runner command;
    - write only under the evidence directory;
    - write `evidence.json` in the bundle format;
    - read other repositories remotely through `git`/`gh` or MCP; use a throwaway shallow checkout only
      if the task allows it;
    - report, never interpret.
  - With `evidence=False`, `danger-full-access` stays rejected, exactly as today.

- [ ] **Step 1: Write the failing tests.**
  - `test_evidence_invocation_uses_full_access`.
  - `test_code_invocation_still_rejects_full_access`.
  - `test_evidence_prompt_names_runner_and_bundle`.
  - `test_only_codex_declares_evidence_support`.
- [ ] **Step 2: Confirm they fail.** Then **Step 3: dispatch the slice.** Then **Step 4: confirm they pass**, along with `tests/test_t15_codex_contract.py` and `tests/test_t16_codex_adapter.py` unchanged.

### Task 8: Ask mode (query) and the `--ask` CLI

**Files:**
- Create: `engine/cld/evidence_mode/ask.py`
- Modify: `engine/cld/cli.py` (the `--ask TASK.json` flag)
- Test: `tests/evidence/test_ask.py`

**Interfaces:**
- **Consumes:** Tasks 2, 5, 6 and 7, plus the existing admission/budget path used by `--step`.
- **Task file:**
  - `{id, kind: "query"|"materialise"|"investigate", env:[names], form: "question"|"sql", brief?: str, sql?: str, output_shape?: str}`;
  - `form: "sql"` requires `sql`; `form: "question"` requires `brief`.
- **Produces:** `run_ask(repo, task: dict, *, executor_spec: str, make_executor=None) -> dict`, which:
  - creates `.cld/runs/ask/<task_id>-<8 hex>/`;
  - writes `task.json` and the brief;
  - dispatches the evidence executor with the runner command line (`python <driver> --sql <file> --env <name> --out <dir> --json`);
  - checks the bundle (Task 6);
  - appends one line to `.cld/runs/ask/ledger.jsonl`;
  - returns `{task_id, status, evidence_dir, problems, runner_used, preview, notes}`. `status` is one of `complete`, `incomplete`, `needs_approval`, `failed` or `blocked`.
- **Preview:** at most 50 rows or 16 KiB of the first result, read lazily.
- **Errors:**
  - An unsupported provider → `blocked` before dispatch.
  - Final executor errors → `failed`, carrying that error.
  - An undeclared environment → `blocked`.
  - A sandboxed lead (the existing `network_block_reason` check) → `blocked`.
- **Ledger concurrency:** ask runs may execute concurrently as separate processes, so append to the ask
  ledger under the existing `cld.locking` file lock.
- **CLI:** `--ask TASK.json --executor SPEC --json`. Exit code 0 for `complete`; otherwise 5.

- [ ] **Step 1: Write the failing tests,** using a fake executor that writes runner records and `evidence.json`.
  - `test_question_query_complete`, `test_sql_form_requires_sql`, `test_undeclared_env_blocked`, `test_unsupported_provider_blocked_before_dispatch`.
  - `test_large_result_preview_is_capped` (Review Focus 4): 100,000 rows → the preview has at most 50 rows and at most 16 KiB.
  - `test_ledger_line_has_no_row_data`.
  - `test_final_error_reported_as_failed`.
  - `test_investigate_ask_returns_findings`.
  - `test_network_disabled_lead_blocked`.
  - `test_concurrent_ask_runs_keep_ledger_intact` (two threads, both lines present and valid JSON).
- [ ] **Step 2: Confirm they fail.** Then **Step 3: dispatch the slice** (`files: engine/cld/evidence_mode/ask.py, engine/cld/cli.py`). Then **Step 4: confirm they pass**, along with the full offline suite.

---

## Sitting 4 — materialise and approval loop

### Task 9: Materialise tasks

**Files:**
- Modify: `engine/cld/evidence_mode/ask.py`, `engine/cld/evidence_mode/bundle.py`
- Test: `tests/evidence/test_materialise.py`

**Interfaces:**
- **Kind `materialise`:**
  - each `created_objects` entry `{name, rows, schema}` is copied into the ask ledger line as `created: [...]`;
  - SQL is kept under `sql/`.
- **Produces:** `list_created(repo) -> list[dict]` in `ask.py`, reading the ledger, for clean-up and rebuild.

- [ ] **Step 1: Write the failing tests.**
  - `test_sandbox_materialise_complete_and_recorded`.
  - `test_real_materialise_without_approval_needs_approval`.
  - `test_list_created_returns_objects_newest_first`.
  - `test_materialise_sql_files_kept`.
- [ ] **Step 2: Confirm they fail.** Then **Step 3: dispatch the slice.** Then **Step 4: confirm they pass.**

### Task 10: Approval CLI and re-dispatch

**Files:**
- Modify: `engine/cld/cli.py` (`--approve TASK_ID --env NAME --statement HASH --reason TEXT [--approved-by NAME]`)
- Test: `tests/evidence/test_approve_cli.py`

**Interfaces:**
- **Consumes:** Task 4 `record_approval`, Task 8 `run_ask`.
- **Rules:**
  - `--approve` records the approval and prints it as JSON.
  - Re-running the same `--ask` task file then lets the runner execute that exact statement.
  - A changed statement (different hash) needs a new approval.

- [ ] **Step 1: Write the failing tests.**
  - `test_approve_then_rerun_executes`.
  - `test_changed_statement_needs_new_approval`.
  - `test_approve_requires_reason`.
- [ ] **Step 2: Confirm they fail.** Then **Step 3: dispatch the slice.** Then **Step 4: confirm they pass.**

---

## Sitting 5 — plan-mode evidence slices, investigate, KB template

### Task 11: Plan format fields

**Files:**
- Modify:
  - `engine/cld/executors/base.py`: `SliceTask.kind: str = "code"` and `SliceTask.environments: list[str] = []`;
  - `engine/cld/plan/slice.py`: parse, validate and serialise `kind` and `environments`.
- Test: `tests/evidence/test_plan_kinds.py`

**Rules:**
- `kind` is one of `code`, `investigate`, `query` or `materialise`.
- `query`/`materialise` require at least one environment and no `files`.
- `investigate` keeps `files` (the module and its freshness file) and `acceptance_test_path`.
- `code` is unchanged.
- Older plans without `kind` parse exactly as before, and the task fingerprint for `kind: code` is unchanged.

- [ ] **Step 1: Write the failing tests.**
  - `test_default_kind_is_code_and_fingerprint_unchanged`.
  - `test_query_requires_environment_and_no_files`.
  - `test_investigate_requires_acceptance_test`.
  - `test_round_trip_markdown`.
- [ ] **Step 2: Confirm they fail.** Then **Step 3: dispatch the slice.** Then **Step 4: confirm they pass**, along with `tests/test_plan_details.py` and the plan/fingerprint tests.

### Task 12: Orchestrator routing for evidence slices

**Files:**
- Modify: `engine/cld/orchestrator.py`, adding routing in plan delivery.
- Test: `tests/evidence/test_plan_routing.py`

**Interfaces:**
- **Consumes:** Task 7 (evidence executor), Task 8 `run_ask`, Task 11 fields.
- **Rules:**
  - **`investigate`:** the existing worktree, allowlist and acceptance-test path, but the executor is built with `evidence=True`.
  - **`query`/`materialise`:** run through `run_ask` with no worktree. The slice is accepted when the bundle status is `complete`; `needs_approval` leaves it resumable at gate 5. The ledger records `evidence_dir`.
  - Dependencies and layers are unchanged.
  - A provider without evidence support blocks before dispatch.

- [ ] **Step 1: Write the failing tests.**
  - `test_investigate_slice_uses_evidence_executor_and_judge`.
  - `test_query_slice_accepted_on_complete_bundle`.
  - `test_materialise_needs_approval_is_resumable`.
  - `test_code_slices_unchanged` (an existing two-slice code plan gives an identical outcome).
- [ ] **Step 2: Confirm they fail.** Then **Step 3: dispatch the slice.** Then **Step 4: confirm they pass**, along with the full offline suite.

### Task 13: Knowledge-base starter template and citation check

**Files:**
- Create:
  - `engine/cld/evidence_mode/kb_template/` containing `knowledge/core.md`, `knowledge/freshness.md`, `knowledge/references/README.md`, `knowledge/references/queries/README.md`, `tests/test_knowledge_contract.py` and `tests/test_citations.py`;
  - `engine/cld/evidence_mode/citations.py`.
- Modify:
  - `engine/cld/cli.py` (`--init-kb DIR`);
  - `pyproject.toml` package data.
- Test: `tests/evidence/test_kb_template.py`

**Interfaces:**
- **Produces:**
  - `verify_citations(text: str, freshness: dict[str, str], *, runner) -> list[str]`, which returns problems. Each `https://<host>/<owner>/<repo>/blob/<ref>/<path>` link is checked with `gh api --hostname <host> repos/<owner>/<repo>/contents/<path>?ref=<sha>`, where the SHA comes from the freshness table for that repository.
  - `--init-kb DIR` copies the template, refusing a non-empty `DIR`.
- **The template:**
  - a size-capped core file with numbered sections (system map, contracts, dependency map, impact chains, risks, key tables/paths, defects, owners, module index);
  - `Verified: <date> against <repo>@<branch>` stamps;
  - a freshness table;
  - an indexed query library whose first lines are comments.

  It contains no real content. The citation test is marked `network`.

- [ ] **Step 1: Write the failing tests.**
  - `test_init_kb_copies_template_and_refuses_nonempty`.
  - `test_template_contract_passes_on_copy` (runs the copied contract test offline).
  - `test_verify_citations_reports_missing_file` (fake runner returns 404).
  - `test_verify_citations_requires_freshness_entry`.
  - `test_template_has_no_real_content` (no hostnames other than `git.example.com`).
- [ ] **Step 2: Confirm they fail.** Then **Step 3: dispatch the slice.** Then **Step 4: confirm they pass.**

### Task 14: Disclosures, guide addendum, regeneration (lead)

**Files:**
- Modify:
  - `README.md`, `PRIVACY.md`, `SECURITY.md` and `KNOWN-ISSUES.md`: evidence tasks run Codex with full access; the two enforcement layers; read-only credentials are required for real environments; MCP-only sources depend on layer 1; artefacts live under `.cld/runs/`;
  - `skill/references/superpowers-to-cld.md` (the evidence-slices section);
  - `CHANGELOG.md` (`[Unreleased]`).
- Test: extend `tests/test_marketplace_disclosures.py` with `test_full_access_evidence_disclosed`.

- [ ] **Step 1: Write the failing test.** Then **Step 2: confirm it fails.** Then **Step 3: write the docs.** Then **Step 4: regenerate and test** (both hosts); the full offline suite passes and `claude plugin validate` shows no new warnings. Then **Step 5: commit.**

---

## After each sitting

1. Run the offline suite.
2. Push the branch and wait for CI **on the user's go-ahead**.
3. Record progress in the local ledger.

There is no release until the user approves. Directory listings track `main`; auto-publish is off.
