# T19B evidence matrix

The lead completed this matrix after the bounded Kimi draft timed out. Fixture
replay proves the isolated bundle's adapter contract, not a live provider call.
OpenCode/Cursor fixtures were captured; Codex/Antigravity fixtures are synthetic
protocol samples. Each row replays success and nonzero-exit with partial edits;
only success captures the actual Git diff. Antigravity usage remains unknown.

| Host | Executor | Replay |
|---|---|---|
| codex | antigravity | offline |
| codex | opencode | offline |
| codex | cursor | offline |
| codex | codex | offline |
| claude-code | antigravity | offline |
| claude-code | opencode | offline |
| claude-code | cursor | offline |
| claude-code | codex | offline |

Windows host discovery is separate evidence: Codex standalone CLI/app-server,
actual VS Code skill invocation, local marketplace/plugin discovery and existing
Claude plugin discovery are recorded in [T14-EVIDENCE.md](T14-EVIDENCE.md) and
[T13B-EVIDENCE.md](T13B-EVIDENCE.md). Those observations cover their recorded CLI,
IDE and plugin versions; no fresh install or global configuration change occurred
in T19B. Actual discovery of the later fourth Codex plugin is unverified; its
packaging/catalog and adapter are offline-tested.

Live Kimi K3/OpenCode under a Codex lead was verified on **Windows only** in T14.
Live `gpt-6-luna@max` Codex execution under a Codex lead was verified on **Windows
only** in [T16-EVIDENCE.md](T16-EVIDENCE.md). The accepted-to-integrated restart
passed; live mid-process interruption remains **unverified**. Live execution
under a Claude lead is not inferred from the same adapters or from host discovery.

Windows/Ubuntu Python 3.11/3.14 offline contracts are verified by CI. macOS
discovery/live behavior, live POSIX execution and actual Ubuntu Codex CLI flag
inspection remain **unverified**. No live POSIX support claim is made. The
provider-independent process-death/fresh-resume proof is [T19A](T19A-EVIDENCE.md),
not a live-provider interruption canary.

T19A recovered **825,553** provider tokens / USD 0.900996 as a **lower bound**,
including 667,450 cache-read tokens; final interrupted-response usage is unknown.
T19B's single isolated CLI call timed out at 90 seconds without text or tool
calls; full usage/cost is unknown. Lead usage is unavailable. Recommended
maintenance defaults are one worker, one production attempt plus any separately
needed validation allowance, exact model pins, unknown-usage denial, concise
briefs and admission budgets. Admission cannot cap an in-flight provider call.
Do not increase timeouts or budgets simply to hide unsuccessful delegation.

See [T19B evidence](T19B-EVIDENCE.md) for measurements, gate results and rollback.
