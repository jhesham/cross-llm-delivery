# Installing cross-llm-delivery skill(s) on another machine

You install **one or more generated per-provider skills** by copying self-contained folders into
`~/.claude/skills/`. Each folder vendors the whole engine (`scripts/cld/`) — **no `pip install`,
no cloning, no building on the target**. You need Python 3.11+ and the executor CLI(s) for the
provider(s) you install.

> `dist/` is gitignored build output. Always hand over a **freshly rebuilt** folder, never a
> checked-out stale one. On the source machine: `python generator/build_skill.py --all`
> (cross-platform; on Windows `pwsh ./rebuild-skills.ps1` is a clean-rebuild convenience wrapper).

> **Platform note:** Windows is the validated platform for all three providers. On macOS/Linux the
> engine/generator/tests are portable and **opencode** is the recommended (proven-path) executor;
> antigravity and cursor dispatch on POSIX is experimental. See the README's Platform support section.

## The runnable providers

| Provider | Folder to copy | Cost | Account needed |
|---|---|---|---|
| **opencode** | `dist/cross-llm-opencode` | **$0** with a free model (`opencode/deepseek-v4-flash-free`); metered otherwise | free opencode account |
| **antigravity** | `dist/cross-llm-antigravity` | flat-rate ($0 marginal) | **Antigravity / Google-AI subscription** |
| **cursor** | `dist/cross-llm-cursor` | metered | **Cursor subscription** |

These three are the only runnable executors. (The Composer model is reachable via the **cursor**
provider as `cursor:composer-2.5`.)

## Can I install several at once? Yes — they don't collide

The generated `dist/cross-llm-<provider>/` folders are **independent and self-contained**, so any
number can live in `~/.claude/skills/` together:

- **Distinct skill names** (`cross-llm-opencode`, `cross-llm-antigravity`, `cross-llm-cursor`) —
  Claude Code registers each as its own skill.
- **No shared package on a global path.** Each folder ships its own vendored `scripts/cld/`, and its
  `run_delivery.py` puts *its own* `scripts/` dir first on `sys.path`. Each run is a separate process
  using its own engine copy — no cross-contamination.
- **No hooks, no shared filenames** between bundles (each is wholly under its own folder).
- **Shared state is intentional and safe:** all skills read/write one global validation-evidence
  file, `~/.cld/validation-evidence.json` — a *feature* (a model you validate once is known to every
  skill), not a collision. The per-build ledger is `.cld-ledger.json` written in the build's working
  directory (the repo you point `--repo` at), so it's scoped to the build, not the skill.

So: install one to start, or install all the runnable ones — your choice.

---

## Install ALL runnable providers

### 1. Copy the three provider skill folders

macOS / Linux:
```bash
mkdir -p ~/.claude/skills
for p in opencode antigravity cursor; do
  cp -r "<source>/dist/cross-llm-$p" ~/.claude/skills/cross-llm-$p
done
# sanity: each must have a vendored engine (not the deprecation stub)
ls ~/.claude/skills/cross-llm-*/scripts/cld/__init__.py
```

Windows (PowerShell):
```powershell
$skills = "$env:USERPROFILE\.claude\skills"
New-Item -ItemType Directory -Force $skills | Out-Null
foreach ($p in "opencode","antigravity","cursor") {
    Copy-Item -Recurse -Force "<source>\dist\cross-llm-$p" (Join-Path $skills "cross-llm-$p")
}
foreach ($p in "opencode","antigravity","cursor") {
    Test-Path (Join-Path $skills "cross-llm-$p\scripts\cld\__init__.py")   # must be True for each
}
```
(Replace `<source>` with the path to the freshly rebuilt repo `dist/`.)

### 2. Install + authenticate each executor CLI

Requirements on the target machine: **Python ≥ 3.11**, **git**, and **Node/npm** (the executor
CLIs are Node-based). Set up each provider you'll use (commands identical on all platforms):

**opencode** ($0 with the free model; free account):
```bash
npm install -g opencode-ai
opencode auth login
opencode run "reply with the single word READY"   # headless verify -> should print output
```

**antigravity** (needs an Antigravity / Google-AI subscription; flat-rate):
```bash
# install the Antigravity CLI so `agy` is on PATH (usually %LOCALAPPDATA%\agy\bin\agy.exe;
# set AGY_CMD if it's elsewhere).
agy --version        # confirms the BINARY only (says nothing about auth)

# MANDATORY one-time interactive login BEFORE any headless use:
agy                  # run it bare in a real terminal, complete the browser sign-in, then exit
```
**Auth caveats (read these — they save an hour):**
- **Login is mandatory before headless use.** `agy` ships installed but **unauthenticated**; logging
  in via the interactive `agy` is what writes its state under `%USERPROFILE%\.gemini\antigravity-cli\`.
- **There is NO `whoami`/`status`/`auth` subcommand**, so there is no scriptable auth check. The only
  thing safe to run non-interactively is `agy --version` (returns e.g. `1.0.10`) — and it proves only
  that the binary exists, NOT that you're logged in. `agy models` requires an interactive terminal.
- **A hang means "log in first," not "broken."** Both `agy models` and `agy -p "…"` **silently hang
  with no error** if you're not authenticated (or if run without a real interactive TTY). If `agy`
  appears to freeze, the cause is almost always missing login — do the interactive `agy` sign-in.
- Confirm auth by running `agy` (or `agy models`) **interactively** once after login: it should list
  your models instead of hanging. `agy -p` writes its reply to a transcript file (not stdout), so it
  won't echo a one-liner — the skill's executor reads that transcript (and forces the working dir onto
  C: for a Windows path quirk). The first real `--step` build is the true end-to-end headless proof.

**cursor** (needs a Cursor subscription; metered):
```bash
# install cursor-agent so it's on PATH (the skill auto-resolves the versioned binary;
# set CURSOR_AGENT_CMD to override). Then log in + verify reachability:
cursor-agent --version
cursor-agent about           # short call -> prints tier + model (confirms auth/reachable)
```
Long-prompt headless dispatch on Windows is handled by the skill via direct-node (validated).

### 3. (single-provider only) If you want just one

Do step 1 for that one folder and step 2 for just that CLI. The recommended lowest-friction $0
choice is **opencode** with `opencode/deepseek-v4-flash-free`.

---

## Choosing which installed skill to use

With several installed, you select per build by **naming the skill** when you ask Claude Code — e.g.
"use **cross-llm-opencode** to run this plan" or "drive this build with **cross-llm-antigravity**."
Each skill drives the same engine; the only difference is which executor backend (and model picker)
it exposes. Within a chosen skill, its first-dispatch picker still lets you pick the specific model.

A rule of thumb: **opencode** for $0/free-tier work, **antigravity** for highest-quality flat-rate
runs (if subscribed), **cursor** for Composer-based runs (if subscribed).

## Running a build (any installed skill)

From the installed skill folder (all platforms):
```bash
python scripts/run_delivery.py <plan.md> --repo <target-repo> --step
```
- `--dry-run` first prints the layers without dispatching (also confirms Python + the vendored
  engine import cleanly — needs no executor CLI).
- The picker offers that provider's models on the first dispatch.

## If something's off
- **`python` not found:** use `py` instead of `python`.
- **Skill folder doesn't import / "no module named cld":** confirm you copied the *generated*
  `dist/cross-llm-<provider>/` folder (it has `scripts/cld/`), NOT the repo's `skill/` folder
  (that's a deprecation stub).
- **Banner check:** `dist/cross-llm-<provider>/SKILL.md`'s first line should read
  `GENERATED from cross-llm-delivery@<sha>` matching the source HEAD.
