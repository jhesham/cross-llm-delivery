# Privacy policy

This policy covers the cross-llm-delivery (`cld`) source repository, its
generated skill bundles and its plugin packages. It describes what the
software does on your machine; it is not a policy for any provider, host or
service you choose to use with it.

Cross-llm-delivery is an independent project; it is not affiliated with or
endorsed by Anthropic or OpenAI. Claude, Claude Code, Codex and other names are
trademarks of their respective owners.

## Summary

- **No publisher collection by default.** The project publisher operates no
  service that CLD requires and receives no prompts, code, logs, telemetry or
  account data from the software. Nothing is sent to the publisher unless you
  choose to share it (for example in a GitHub issue or pull request).
- **Your selected tools do send data.** The executor CLI you select, and any
  optional export or grading you configure, can send prompts, repository
  content and metadata to the provider or endpoint you configured. CLD does not
  route all network traffic through one CLI and does not control those
  recipients' retention.
- **Local records are kept until you remove them.** Worktrees, `refs/cld/*`,
  the ledger, event streams and logs stay in your repository/filesystem until
  you deliberately clean them up.

## Data categories and purposes

| Category | Where it comes from | Purpose |
|---|---|---|
| Plans, slice briefs, acceptance tests and repository content | Your plan and target Git repository | Build executor prompts, create candidate worktrees, run acceptance and integration tests |
| Prompts and executor output | Generated from your plan; returned by the selected CLI | Implement slices; retained as diagnostics for review and recovery |
| Candidate diffs, commits and refs | Executor worktrees | Independent acceptance, integration and recovery (`refs/cld/*`) |
| Test, process and hook output | pytest, Git hooks, project commands, executor CLIs | Acceptance/integration verdicts and diagnostics |
| Run events and status | The engine | Local status, budget accounting and recovery (`.cld/runs/<run-id>/events.jsonl` and related files) |
| Model, effort, token usage and costs where reported | Executor CLI output | Budget admission and reporting; missing usage stays unknown |
| Validation identity | CLI binaries, selected config files and selected environment variables | Decide whether existing model-validation evidence still applies |

### Validation identity and credentials

To decide whether validation evidence is still current, the engine
(`engine/cld/admission.py`) records CLI and configuration file paths with
SHA256 content hashes, and the **names** of selected environment variables
(for example proxy/CA variables and provider-specific variables such as
`OPENAI_*` or custom provider `env_key` names). The selected environment
**values**, which can include API keys or tokens, are read in memory and
contribute only to a SHA256 fingerprint; the values themselves are not written
to the ledger.

A SHA256 fingerprint is **not encryption or anonymization**. Anyone holding the
ledger can test guesses against it, and low-entropy values (short tokens,
predictable account names, common proxy URLs) may be inferred. Treat ledgers
and run directories as sensitive.

CLD does not claim it never reads credentials. Executor CLIs use their own
authentication files, keyrings and configuration under your account. For the
Codex executor, authentication files and keyrings are deliberately excluded
from validation evidence, so switching accounts needs explicit
`--revalidate-models` and a stable non-secret `--validation-context`. See the
selected bundle's `references/provider-setup.md` for each provider's details.

## Recipients

| Recipient | When | What |
|---|---|---|
| Your selected executor provider (through its CLI and your configured endpoints) | Dispatch and validation (`--step`, validation probes) | Prompts, slice briefs, repository content the CLI reads, and whatever the CLI itself sends under its own policy |
| Anthropic API | Only if you use the optional DeepEval behavioral grading library facility with `ANTHROPIC_API_KEY` set | Grading inputs |
| Your configured OTLP endpoint (or Langfuse) | Only if `OTEL_EXPORTER_OTLP_ENDPOINT` (with optional `OTEL_EXPORTER_OTLP_HEADERS`) or `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` is set and the OpenTelemetry SDK is installed | Dispatch span metadata (see below) |
| Anything your project's tests, hooks or commands contact | Acceptance/integration runs | Whatever those subprocesses send; they run with your privileges and network access |
| The project publisher | Only when you post an issue, pull request or private security report | What you choose to include |

### Telemetry

Local event recording is always on during execution; it is how status,
budgets and recovery work. There is **no external telemetry export unless you
configure it**. When configured, OTLP export currently sends dispatch metadata:
model, slice ID, rung, source, attempt, return status, duration and token
usage. It does not export raw prompts. However, local logs and provider output
may contain sensitive material, and CLD does **not** guarantee that logs,
events or provider output are redacted.

## Executor authentication and billing

| Executor | Credentials and environment | Billing |
|---|---|---|
| Claude Code CLI | Deliberately removes `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_BASE_URL` from the executor environment and requires a claude.ai subscription login (`authMethod: "claude.ai"`); each slice runs in an isolated session with no saved session | Your Claude plan's usage limits |
| Codex CLI | Uses the installed CLI and your Codex authentication/configuration; no removal list is applied | Your plan, API or configured provider billing, as applicable |
| OpenCode, Cursor, Antigravity | Use the installed CLI, your account and its configuration; no removal list is applied | Your plan, API or configured provider billing, as applicable |

CLD charges no separate inference fee. Dollar costs may be unknown when a CLI
does not report them. Provider plans, data use and retention are governed by
your provider account and its policies; CLD makes no guarantee about them.

## Local persistence and retention

CLD keeps, in or beside the target repository:

- managed Git worktrees and `refs/cld/*` recovery/integration refs;
- the ledger (`.cld-ledger.json` by default; a custom ledger path can place it
  elsewhere);
- `.cld/` run directories with events, summaries, prompts/output logs and
  process diagnostics.

These remain until you deliberately clean them up. CLD performs **no automatic
deletion or redaction**. The safe cleanup preview (`--gc --repo <dir> --json`)
and `--gc --apply` are scoped engine controls: they remove only CLD-managed
worktrees proven safe to remove and never delete run evidence or refs. Preserve
recovery evidence before removing anything else; see
[KNOWN-ISSUES.md](https://github.com/jhesham/cross-llm-delivery/blob/main/KNOWN-ISSUES.md)
and the [README](https://github.com/jhesham/cross-llm-delivery/blob/main/README.md).

Git history (including integrated commits), provider CLI caches, sessions and
authentication have separate lifecycles managed by Git and by each provider.
Provider-side retention follows your account's policies, not CLD guarantees.

## Your controls

- Choose which executor, model and endpoints receive data; preview with
  `--dry-run --json`, which makes no executor call.
- Leave OTLP/Langfuse variables and `ANTHROPIC_API_KEY` unset to avoid those
  optional exports/grading.
- **Do not paste secrets** into plans, briefs, tests, logs, support requests,
  issues or submission files. Briefs and repository content are sent to the
  selected provider.
- Review and redact logs before sharing them.
- Remove worktrees, refs, ledgers and run directories deliberately once you no
  longer need recovery evidence.

## Contact

Public questions and support:
[GitHub Issues](https://github.com/jhesham/cross-llm-delivery/issues).
Vulnerabilities and anything confidential: use private vulnerability reporting
as described in [SECURITY.md](SECURITY.md); do not post secrets publicly.
