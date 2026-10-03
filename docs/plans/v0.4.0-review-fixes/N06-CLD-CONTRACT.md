# N06 executor contract — consistent recursion defense

Implement only the recursion finding. This is defense against accidental nested
spend, not an OS sandbox. Acceptance uses local Python children and synthetic
capability probes; no other provider is called.

- A lead has CLD_EXECUTOR_DEPTH absent or the exact string `0`. Every other value
  (including empty, malformed or alternate zero spellings) blocks direct `.run`
  consistently before any probe, command resolution, artifact creation or diff
  capture. The existing CLI already uses this rule. Reuse a small shared helper
  if useful; keep the core provider-agnostic.
- All five production executor children must have CLD_EXECUTOR_DEPTH=`1`.
  Preserve other environment adjustments: inherited values, Cursor's
  CURSOR_INVOKED_AS and bundled-Node TLS options, Codex launcher env, Claude's
  effort and credential removals. Do not mutate the lead's os.environ.
- Preserve the injected legacy runner(argv, cwd) two-argument contract. Add
  dispatch environment kwargs only on its production runner path. Cursor's
  default runner must merge an incoming env overlay with its own adjustments,
  avoiding duplicate env keyword errors or discarded settings.
- Keep probe/lifecycle deadlines, cancellation, retained logs and diff capture
  unchanged. Do not mark unrelated shared run_process calls as executor calls.
- OpenCode, Cursor and Antigravity prompts must identify a one-slice executor
  and prohibit invoking CLD, another provider or a dispatch tool, including
  feedback/retry prompts. Codex/Claude already put this role in their contracts.
- Touch only engine/cld/process.py and the five provider.py files listed in the
  plan. No tests, contract files, generated artifacts, resolver/N07 changes,
  Antigravity cwd/N08 changes, CLI, global settings or package installation.

## Efficient validation on this Windows machine

Read the acceptance file and relevant provider sections; implement the bounded
change once. Run only tests/test_n06_recursion_contract.py, with pytest plugin
autoload disabled. If shell/test access fails with the known restricted-token
temporary-directory PermissionError or sandbox helper error, report it promptly
and stop retrying. Do not invent temp directories, broaden grants, install tools,
relax tests, or spend turns debugging this environment. The lead's independent
CLD acceptance/integration performs the decisive verification.

No Git mutations or other model calls. Summarize changes and any access limits,
then finish the turn.
