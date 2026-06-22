# Installing a cross-llm-delivery skill on another machine

You install **one generated per-provider skill** by copying a single self-contained folder into
`~/.claude/skills/`. The folder vendors the whole engine (`scripts/cld/`) — **no `pip install`,
no cloning, no building on the target**. You only need Python 3.11+ and the one executor CLI that
your chosen provider drives.

> `dist/` is gitignored build output. Always hand over a **freshly rebuilt** folder, never a
> checked-out stale one. On the source machine: `pwsh ./rebuild-skills.ps1` (wipes `dist/` and
> regenerates every live provider from HEAD, smoke-check ON). The deleted `gemini` provider can no
> longer be produced.

## Which provider? (recommendation for a fresh single machine)

| Provider | Cost | Setup friction | Notes |
|---|---|---|---|
| **opencode** (recommended for a fresh box) | **$0** with a free model (`opencode/deepseek-v4-flash-free`) | npm install + free login; clean one-line headless check | No paid subscription. Best "just works at $0" path. |
| **antigravity** | flat-rate ($0 marginal) | needs an Antigravity / Google-AI subscription; reply lands in a transcript file (no stdout) | Highest quality (Gemini 3.1 Pro / Claude); the verified default workhorse. Pick this if you already have the subscription. |
| cursor | Cursor subscription (metered) | needs cursor-agent + login | Composer 2.5; direct-node dispatch on Windows. |
| composer | — | — | Stub, not runnable. |

**Recommended: `opencode` with `opencode/deepseek-v4-flash-free`** — zero cost, no subscription,
and a one-command headless verify. Use `antigravity` instead if you have the subscription and want
top quality.

---

## Option A — opencode (recommended, $0)

1. **Copy the skill folder** (from the freshly rebuilt `dist/` on the source machine):
   ```powershell
   Copy-Item -Recurse <source>\dist\cross-llm-opencode "$env:USERPROFILE\.claude\skills\cross-llm-opencode"
   ```
2. **Install the executor CLI** (needs Node/npm):
   ```powershell
   npm install -g opencode-ai
   ```
3. **Authenticate** (free account):
   ```powershell
   opencode auth login
   ```
4. **Verify it's reachable headless** (one command — should print a short reply, not hang):
   ```powershell
   opencode run "reply with the single word READY"
   ```
   If that prints model output, the executor is reachable. You're ready to run a build with the
   free model `opencode/deepseek-v4-flash-free` (the skill's picker will offer it).

## Option B — antigravity (flat-rate, top quality)

1. **Copy the skill folder:**
   ```powershell
   Copy-Item -Recurse <source>\dist\cross-llm-antigravity "$env:USERPROFILE\.claude\skills\cross-llm-antigravity"
   ```
2. **Install the Antigravity CLI** so `agy` is on PATH (typically `%LOCALAPPDATA%\agy\bin\agy.exe`;
   override with `AGY_CMD` if elsewhere).
3. **Authenticate (interactive, one time):** run `agy` on its own and complete the browser login.
4. **Verify install + auth:**
   ```powershell
   agy --version            # confirms the binary
   agy models               # in an interactive terminal, lists your models (confirms auth)
   ```
   Note: `agy -p` writes its reply to a transcript file, not stdout, so it won't echo a one-liner —
   the skill's executor handles that (and forces the working directory onto C: for a Windows
   transcript-path quirk). The first real `--step` build is the end-to-end headless proof.

---

## Running a build (either provider)

From the installed skill folder, drive the plan one DAG layer at a time:
```powershell
python scripts\run_delivery.py <plan.md> --repo <target-repo> --step
```
- `--dry-run` first prints the layers without dispatching (also a quick check that Python + the
  vendored engine import cleanly: it needs no executor CLI).
- The picker offers the provider's models on the first dispatch; pick the free/flat one.

## If something's off
- **`python` not found:** the target has Python 3.12 — use `py` instead of `python` if needed.
- **Skill folder doesn't import:** confirm you copied the *generated* `dist/cross-llm-<provider>/`
  folder (it has `scripts/cld/`), NOT the repo's `skill/` folder (that's a deprecation stub).
- **Banner check:** `dist/cross-llm-<provider>/SKILL.md`'s first line should read
  `GENERATED from cross-llm-delivery@<sha>` matching the source HEAD.
