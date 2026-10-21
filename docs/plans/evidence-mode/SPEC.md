# CLD v0.5 — evidence mode (investigate, query, materialise) and the plan-conversion guide

Status: approved design, 2026-10-18.

## 1. Intent

Evidence mode targets **system analysis and data analysis** work:
- understanding a repository and every system upstream and downstream of it;
- turning that understanding into a knowledge base that later powers a dedicated "system agent";
- running data analysis on warehouse data;
- sometimes materialising datasets for proof-of-concept work or further analysis.

An expensive lead model (for example Claude Opus at medium effort) should be the **brain**: it frames,
reasons, interprets and validates. Cheaper, capable executors (for example `codex:gpt-6-luna@max`)
should be the **hands**: they read other repositories, write and run SQL, and materialise data, then
return complete evidence.

Today CLD can only dispatch **code-change slices** judged by acceptance tests. v0.5 adds **evidence
tasks**, whose output is evidence rather than a diff, delivered through the same executors, ledger,
budgets and final-error handling.

The hand-off from a superpowers plan into a CLD plan should also be written down, so it is
repeatable (§9).

## 2. Who carries trust (decided)

**CLD is a pipe. The lead owns truth.**

- **CLD:**
  - delivers a task to an executor;
  - returns everything that happened, faithfully and completely;
  - enforces the safety boundary on real environments;
  - records the run in the ledger.

  CLD does **not** judge whether an answer is correct.
- **The lead:**
  - interprets every result and owns the conclusions;
  - validates in proportion to what rides on the answer: reading the returned SQL, re-running a key
    figure, checking a total against a known value, or asking a second executor;
  - with a frontier-class executor this is usually light, but it is always the lead's job.
- **The executor:**
  - does the legwork and reports what it did, including anything it changed or assumed;
  - never interprets results.

## 3. Goals

1. **Ask mode.** The lead sends a single evidence task and gets the evidence back, quickly and
   repeatedly, without writing a plan file. This is the analysis loop.
2. **Evidence slices in plan mode.** A fixed set of evidence tasks with dependency layers, for
   knowledge-base builds and multi-step materialisations.
3. **Three kinds of evidence task:**
   - **Investigate:** read one system (a repository through `git`/`gh`, or an MCP-reachable source)
     and write a findings file in a format the lead defines.
   - **Query:** answer a data question. The lead chooses per task between:
     - **question form:** a plain-words question plus context (tables, keys, environment); the
       executor writes, runs and repairs the SQL;
     - **SQL form:** the lead's drafted SQL; the executor runs it, and if it errors, repairs it and
       says what changed.

     Either way the returned SQL is exactly what ran.
   - **Materialise:** create a dataset (for example `CREATE TABLE … AS SELECT`, loads, joins, moves
     across environments or warehouses) in a declared environment, and return what was created.
4. **Environments.** Declared up front, each one named and classed as either:
   - **sandbox:** reads and writes allowed;
   - **real:** read-only; any write stops for approval by the user or the lead.

   Access always comes from the user's existing authenticated tools (`gh`, `gcloud`/`bq`, MCP
   servers). CLD never handles credentials.
5. **Complete, traceable evidence.** Every task returns:
   - for a query or materialisation: the exact SQL that ran, the result as a file (or the created
     object), and the run statistics (rows, bytes scanned or cost where the platform reports it,
     duration, job ID);
   - for an investigation: the findings file plus the commit or version of each source read;
   - always: the executor's note of changes, assumptions and errors.

   Evidence missing any required part comes back **flagged as incomplete**; it is never presented as
   a normal result.
6. **Ledger and audit.** Every evidence task and every run against a real environment is recorded,
   including objects created (table, view, location), so the lead can audit, rebuild or clean up.
7. **Knowledge-base builds.**
   - One investigate slice per neighbouring system.
   - Each slice writes only its own module and its freshness entry.
   - Acceptance uses the knowledge base's own **contract tests** (structure, required sections,
     freshness stamps, source links). That checks structure, not truth.
   - Also checked: **every file or path cited exists at the recorded commit** of that system.
8. **Materialisation reproducibility.** The SQL of every materialisation is kept as files, so a
   successful proof of concept can later become real pipeline code through a normal CLD build.
9. **The superpowers → CLD plan guide** (§9).

## 4. Non-goals

- CLD judging analytical correctness, or adding semantic "sanity" gates. That is the lead's job.
- Mandatory cost controls: no dry runs before queries, and no per-environment cost limits. Actual
  run statistics are recorded after the fact.
- Scheduling or running production pipelines (orchestrators, recurring jobs). Pipeline *code* is
  built through normal CLD plan mode and deployed by the user.
- Generating the system agent or skill from a knowledge base. CLD's job ends at a complete knowledge
  base that passes its tests.
- Automated knowledge-base refresh. Re-dispatching investigate slices for systems a drift check flags
  should work with the same mechanism, but drift detection is not part of v0.5.
- Permanent local clones of other repositories. Read remotely through `git`/`gh` or MCP by default; a
  throwaway shallow checkout is an opt-in fallback only.

## 5. Anti-goals (would make this a failure even if it works)

- A write reaching a real environment without explicit approval.
- Evidence that cannot be traced:
  - a number without the SQL that produced it;
  - SQL presented as run when a different, repaired version actually ran;
  - findings citing files that do not exist.
- CLD holding, copying or logging credentials.
- Weakening any existing guarantee of code-change slices (acceptance, allowlists, integration gate).
- Forcing a plan file for every single analysis question.

## 6. Constraints

- **Stack and compatibility:**
  - stdlib Python, 3.11+, Windows and POSIX;
  - the existing provider packages (Codex, Claude, OpenCode, Cursor, Antigravity) remain the
    executors;
  - existing code-change behaviour is unchanged.
- **Executors and the network:**
  - executors need network and read access outside their worktree (`gh`, `gcloud`, MCP);
  - the executor launch must allow that;
  - a sandboxed lead (for example Codex with network disabled) must be blocked with a clear message
    before dispatch, as today.
- **Ledger safety:**
  - results can be large: store result files as run artefacts under `.cld/runs/`;
  - never put row data in the ledger itself;
  - never store credentials or secrets in evidence or logs, including connection strings in SQL
    error text.
- **Privacy:** evidence may contain sensitive data. Retention is local, as today, and documented in
  PRIVACY.md.

## 7. Decided behaviour (how it should work)

### 7.1 Environments

- A project-level environment file, read by the lead and by CLD, names each environment. For each it
  gives:
  - its class (`sandbox` or `real`);
  - its platform (for example BigQuery, Postgres, a git host or an MCP source);
  - how to reach it (which CLI or MCP server, project, dataset or host).
- **Every task names its environment(s).** A task touching an undeclared environment is refused.

### 7.2 The write rule

- In a `real` environment, the executor may only read.
- Any statement or tool action that writes, deletes, alters schema, or moves data into that
  environment must pause the task for approval, recorded in the ledger.
- In a `sandbox`, writes are allowed.
- **Detection must fail closed:** if CLD cannot tell whether an action writes, treat it as a write.

### 7.2a Enforcement, two layers (decided: option c)

**Layer 1: platform read-only access, the real protection.**
- The user gives each `real` environment read-only credentials or roles. Examples:
  - BigQuery: data viewer plus job user, with no data editor;
  - a read-only MCP connection.
- The warehouse itself then refuses writes.
- The environment file records that the environment is expected to be read-only.
- CLD documents how to set this up per platform. It does not create credentials.

**Layer 2: the CLD SQL runner, a second check.**
- A CLD command runs SQL for a named environment, using the user's own `gcloud`/`bq` (or other
  platform CLI) authentication. It:
  - classifies each statement, using the platform's own statement-type metadata where available;
  - fails closed on anything unclassifiable;
  - blocks writes to `real` environments unless an approval is recorded;
  - captures the exact SQL, the result file and the run statistics as evidence.
- Evidence-task executors are instructed to run all SQL through this runner.
- **MCP-only sources:**
  - SQL issued directly through an MCP tool bypasses layer 2, so for those sources layer 1 is
    mandatory;
  - CLD records the MCP calls the executor reports;
  - CLD marks the evidence "runner not used" so the lead knows which layer applied.

### 7.2b Executor permissions for evidence tasks (decided)

- **Access:** evidence tasks run executors with **full access** — network, reading outside the
  worktree, and the user's `gh`/`gcloud`/MCP setup. This matches the earlier no-sandbox decision for
  the Claude executor.
- **Protection** comes from:
  - layer 1 (platform read-only access);
  - layer 2 (the SQL runner);
  - evidence and result artefacts being written only under `.cld/runs/`.
- **Codex:** this means relaxing its sandbox for evidence tasks only. Code-change slices keep their
  current sandbox and behaviour.
- **Documentation:** the permission inventory in README, PRIVACY.md and SECURITY.md must disclose
  this before release.

### 7.3 Ask mode

- A CLI entry point takes one task, given inline or as a small file:
  - the kind (investigate, query or materialise);
  - the environment(s);
  - the form (question or SQL);
  - the brief or SQL;
  - an optional required output shape.
- It dispatches to the chosen executor and returns the evidence bundle as JSON for the lead.
- Several tasks may be dispatched concurrently.
- It uses the existing validation evidence, budgets and final-error rules.

### 7.4 Plan mode

- Evidence slices use the existing plan format, plus fields for the kind, environment and expected
  outputs.
- Dependency layers work as they do today. Materialisation steps chain naturally: staging, then
  joins, then the final dataset.
- Code slices and evidence slices may coexist in one plan.

### 7.5 Investigate slices for knowledge bases

- The lead first commits the knowledge base contract tests and a module template, failing because
  the modules do not exist yet.
- Each slice:
  - receives one system and a brief;
  - writes only its module plus its freshness entry (repository, branch, verified commit, date);
  - is accepted when its contract tests pass and its citations verify at the recorded commit.
- Integration means the whole knowledge base passes its contract tests.
- **Reference shape** for a system knowledge base:
  - a size-capped core file with fixed numbered sections;
  - one module per neighbouring system, each with a `Verified: <date> against <repo>@<branch>`
    stamp and source links;
  - a freshness table of verified commits;
  - an indexed library of read-only queries, each headed with the question it answers and its
    recorded result;
  - contract tests enforcing all of the above.

  CLD should ship a **starter template** of that shape, with no content.

### 7.6 Query tasks

- **The result is a file:**
  - CSV or JSON, with a row cap on what is returned inline to the lead;
  - the full result kept as an artefact.
- **Queries worth keeping:** the lead may ask that a query be added to a query library (file plus
  index entry: question, environment, recorded result, date).

### 7.7 Materialise tasks

- Return the created object(s):
  - fully qualified name;
  - row count;
  - schema;
  - the SQL that created them, saved as files.
- Each created object is recorded in the ledger for clean-up and rebuild.

## 8. Left to the builder

- **File formats:** the environment file and the evidence bundle's JSON schema.
- **Write detection inside the SQL runner (§7.2a):** how to classify statements per platform, as
  long as it fails closed.
- **Ask mode:** CLI naming and flags.
- **Concurrency:** the concurrency model.
- **Result handling:** the size limits for inline results and where artefacts live.
- **Citation verification:** how it works for git hosts and for MCP sources.
- **Starter template:** layout and tests.
- **Provider support:** which providers support evidence tasks in v0.5. Codex first is acceptable;
  others must report "not supported" cleanly, never pretend.
- **Code-slice reuse:** how much of the code-slice machinery (worktrees, judge) evidence slices
  reuse, and what they bypass.

## 9. Superpowers plan → CLD plan guide (docs)

A short reference in the skill bundle (`skill/references/`) explaining how a lead converts a
superpowers implementation plan into a CLD plan:

| Superpowers plan | CLD plan |
|---|---|
| A task | One `## SLICE:` block |
| The task's test file | `acceptance_test_path`, committed failing first |
| The task's "Files: create/modify" list | `files`, the writable allowlist |
| Task ordering / dependencies | `deps` |
| The plan's Global Constraints | Repeated in each slice `brief`, or in protected inputs |
| Task size | Optional `complexity` |
| A task with no test | Not a slice: the lead does it, or adds a test first |

The guide covers:
- choosing the integration selector per layer;
- when to split or merge tasks;
- the red-baseline rule (tests fail by assertion, not import error);
- an end-to-end example of a lead model planning with superpowers and building through
  `codex:gpt-6-luna` slices;
- the same guidance for evidence slices (§7.4), once evidence mode exists.

It ships first, independently of the engine work.

## 10. Delivery

- Plan with superpowers writing-plans; build through CLD where slices are contract-testable.
- **Order:**
  1. the guide (§9);
  2. environments and the write rule;
  3. ask-mode query tasks;
  4. materialise;
  5. investigate slices and the knowledge-base starter template.
- No release, push or publication without the user's go-ahead.
- Directory listings track `main`, and their publication stays under the user's control.

## 11. Calls made in this design (for the user to check)

- **Approval for a blocked write.** The task stops and returns the proposed statement as a "needs
  approval" result. The lead (or the user) approves it explicitly, the approval is recorded in the
  ledger, and the task is re-dispatched with that approval. There is no interactive prompt inside a
  headless executor.
- **Where investigate output goes.** An investigate slice writes its module file in the knowledge-base
  repository through the normal worktree and allowlist. Ask-mode evidence goes to `.cld/runs/`.
- **Ask-mode results.** Results are returned to the lead as a capped preview plus the artefact path,
  so large results do not flood the lead's context.
- **Delivery order.** The plan-conversion guide ships first because it is independent and useful
  immediately.
