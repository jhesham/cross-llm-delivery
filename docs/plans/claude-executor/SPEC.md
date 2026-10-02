# Claude Code executor provider — design (v0.4.0)

Status: design approved in conversation 2026-10-01; awaiting written-spec review.
Scope: a fifth executor provider, `claude`, so either lead host (Codex or Claude
Code) can dispatch slices to Claude models headlessly through the `claude` CLI.
Out of scope: review findings R01–R06 from `docs/plans/v0.3.1-fixes/REVIEW-2026-10-01.md`
(a separate sub-project gating the v0.4.0 tag); R07 is fixed here because the
shared launcher replaces that code.

## Goal and success criteria

A Codex lead (e.g. `gpt-6-astra`) or a Claude lead can deliver slices with a
Claude executor under every existing CLD guarantee: committed red acceptance
tests, independent candidate verification, protected inputs, admission and
validation evidence, accounting where unknown usage is never zero, verified
integration, nothing merged into the user's checkout.

- A Codex lead completes a two-slice plan with `claude:claude-sonnet-5@low` to
  verified integration on Windows (live canary, user-authorized spend).
- Offline CI (Windows/Ubuntu × Python 3.11/3.14) covers the contract, launcher,
  preflight, accounting and generated bundles for both hosts.
- Ten standalone skills and five plugin packages per host build and pass
  freshness/release checks.

## Decisions (from brainstorming)

1. **Billing:** the user's Claude subscription through the logged-in `claude`
   CLI only. No API-key billing path.
2. **Isolation:** the executor session loads none of the user's customizations.
3. **Shell:** no OS sandbox; the shell runs with the user's privileges, the same
   documented boundary as OpenCode, Cursor and Antigravity.
4. **Models:** exact IDs only; aliases rejected; a curated picker menu.
5. **Architecture:** a provider package mirroring the Codex adapter, plus one
   shared native-CLI launcher module. Stdlib only.

## Invocation and isolation

One fresh, non-interactive session per dispatch, cwd = the slice worktree:

```
<native claude executable> -p --output-format json
  --model <exact-id> --effort <low|medium|high|xhigh|max>
  --safe-mode --restricted
  --strict-mcp-config --mcp-config {"mcpServers":{}}
  --tools Read,Edit,Write,Glob,Grep,Bash
  --permission-mode dontAsk --allowed-tools Read,Edit,Write,Glob,Grep,Bash
  --settings {"autoMemoryEnabled":false}
  --no-session-persistence
```

- `--safe-mode` disables CLAUDE.md, skills, installed plugins, hooks, MCP
  servers, custom agents and commands, while auth and model selection still
  work. `--restricted` confines file tools to the working directory, refuses
  `bypassPermissions`, and gates writes to settings and git files.
  `--strict-mcp-config` with an empty config is
  defence in depth. Never `bypassPermissions` or `--dangerously-skip-permissions`.
- The prompt travels on **stdin**, never argv: a role preamble (exactly one
  slice; only the allowed files; no git commit/push or other Git mutation; do
  not invoke CLD, `claude`, `codex` or any other model/dispatch tool) followed by
  the brief, the exact allowlist, the acceptance test path, and any judge
  feedback.
- Child environment: remove `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and
  `ANTHROPIC_BASE_URL` so billing can only use the subscription login; set
  `CLD_EXECUTOR_DEPTH=1`. The existing ambient-depth guard refuses dispatch
  when already inside an executor. A Claude lead with a Claude executor is
  allowed (separate child process, isolated session).
- Capability gate (model-free, before dispatch): `claude --version` must name
  Claude Code with a semantic version; `claude --help` must list every flag
  above. Missing → final `missing_capability`.
- Live probe (2026-10-02, CLI 2.1.286): `--restricted` did **not** block an
  edit to `pyproject.toml`, so slices may edit project configuration files on
  their allowlist; CLD's allowlist and protected-input checks still govern
  what can be accepted. The earlier assumed limit does not apply.

## Results, accounting and errors

`--output-format json` returns one result object. A dispatch is a valid
completion only if: exit code 0; stdout is exactly one JSON object with
`type == "result"`, `subtype == "success"` and `is_error == false`; and the
requested model ID is a key of `modelUsage`. Any other shape (empty, truncated,
extra output, error subtype) never permits diff capture. On valid completion
alone, the shared capture runs; CLD's independent verifier decides acceptance.
The model's `result` text is never evidence.

Usage mapping into the shared accounting layer:

| CLI field | CLD field |
|---|---|
| `usage.input_tokens` | `input` |
| `usage.output_tokens` | `output` |
| `usage.cache_read_input_tokens` | `cache_read` |
| `usage.cache_creation_input_tokens` | `cache_write` |

`total` is derived from input + output (cache categories never added). Missing
fields stay unknown. `total_cost_usd` is recorded in the raw usage record as a
**CLI estimate**, never as provider-reported spend: `cost` stays unknown, so
`--budget-cost` does not apply; token and attempt budgets do. A timed-out
session yields no result object; its usage is unknown.

New final executor errors, added to the shared `FINAL_EXECUTOR_ERRORS` (one
dispatch, no retry, no escalation, gate 5, slice resumable):

| Error | Trigger | Action in message |
|---|---|---|
| `usage_limit` | subscription usage limit reported | wait for the limit window to reset |
| `model_mismatch` | `modelUsage` lacks the requested model (fallback) | the requested model did not run |
| `not_logged_in` | the CLI reports no authentication | run `claude auth login` |

Existing mappings are unchanged (timeout, launch, network, missing capability).
Error subtypes other than the above remain retryable.

## Launcher

A new shared module, `engine/cld/native_cli.py`, resolves a CLI's native
executable without a shell. The Codex launcher keeps its exact resolution order
through this helper. Claude order:

1. `CLAUDE_CLI_CMD` — an absolute path to an existing file, else an error;
2. `claude.exe` on PATH (`claude` on POSIX);
3. behind an npm `claude.cmd` shim: `<shim dir>/node_modules/@anthropic-ai/claude-code/bin/claude.exe`
   (the target the shim itself invokes).

Shim-only → gate 5 naming `CLAUDE_CLI_CMD`; never dispatch through `cmd.exe`.
Native resolution is enabled by the identity of the **process** runner alone,
so injecting a Git runner no longer disables it (fixes review R07 for Codex).

## Preflight, admission and validation evidence

`Provider.launch_problem` for `claude` runs, once per build and model-free:
the launcher; `claude auth status` (JSON) requiring `loggedIn: true` and
`authMethod: "claude.ai"` — anything else, including API-key auth, blocks with
gate 5; and the capability gate.

Validation context for a Claude spec includes: the resolved binary identity;
`context_env = ("CLAUDE_CLI_CMD", "CLAUDE_CONFIG_DIR", "ANTHROPIC_*")` plus the
shared proxy/certificate variables (values hashed, never stored); and the
account's `orgId` and `subscriptionType` from `auth status` as validation-context
`extra`, so an account or plan change forces revalidation. Evidence is per exact
spec (`claude:claude-sonnet-5@low` ≠ `@high`). Subscription usage is classified
`metered-unknown`: a validation probe requires `--validation-policy allow`.

## Spec grammar and picker

`--executor claude:<exact-id>@<effort>`; effort ∈ low, medium, high, xhigh, max.
Aliases (`sonnet`, `opus`, `fable`, `haiku`) and any `+tier` suffix are rejected
locally. The picker offers `claude-sonnet-5`, `claude-opus-5-5`,
`claude-fable-5-1` and `claude-haiku-4-5`, each `untested`, `metered-unknown`,
labelled subscription, default effort `low`. Any other exact ID still works via
`--executor`. Discovery makes no model call and does not imply plan access.

## Packaging and documentation

Generators and release checks iterate registered providers: five standalone
skills and five plugins per host; both marketplaces list `cross-llm-claude`.
Provider `setup.md` and skill fragment cover subscription login, the
unsandboxed shell, Pro-plan limits, curated IDs, isolation flags and the
`--restricted` limit. README provider tables, KNOWN-ISSUES and CHANGELOG are
updated.

## Testing and live evidence

Offline, red-first: contract (capability parse, invocation builder, result
parser), every result subtype and error mapping, model mismatch, child-env
stripping, launcher steps (including the R07 regression), preflight via a fake
`auth status`, evidence-context keys, picker rows, bundles. Result fixtures are
captured from a real run, not invented.

Live, each step needing the user's spend approval: (1) an isolation probe with
`claude-haiku-4-5@low` and a trivial prompt, confirming the JSON shape and
`modelUsage` keys, that no hooks/MCP/skills loaded, that nothing reached
claude-mem, and the `--restricted` configuration-file behaviour; (2) normal
validation of the chosen spec; (3) the Codex-lead two-slice canary.

## Delivery outline (detailed in PLAN.md)

1. Lead: spec + plan; shared launcher with R07 fix; red tests; CLD plan.
2. CLD dogfood (detached; `codex:gpt-6-luna@max+fast`): contract parser,
   picker catalog, preflight helpers.
3. Lead: provider wiring, isolation, accounting, evidence; live probe, fixture
   capture, Codex-lead canary.
4. Lead: docs, regeneration, CI, install.

## Release gate

The review findings R01–R06 are fixed in their own sub-project before the
v0.4.0 tag. Merging to `main`, tagging and publishing require the user's
explicit go-ahead.
