# Claude executor — handoff (2026-10-02)

**Status:** implemented, live-verified and green; on `refactor/codex-support`
(`e5c5e88`, pushed). Not released. See [SPEC](SPEC.md), [PLAN](PLAN.md) and
[EVIDENCE](EVIDENCE.md).

- CI [36974672671](https://github.com/jhesham/cross-llm-delivery/actions/runs/36974672671):
  Windows/Ubuntu × Python 3.11/3.14, all 14 steps per job. The previous run failed
  only at the `ci.yml` inline Codex catalog check, which pinned four plugins; it
  now expects five.
- Full local offline suite: 1178 passed.
- Live (Windows, Claude Code CLI 2.1.286, Pro subscription): isolation probe,
  validation + one-slice delivery, and a Codex-lead (`gpt-6.1-sol`, high)
  two-slice build to gate 3.
- Five Claude-host skills installed globally from `e5c5e88` (backup
  `~/.claude/skill-backups/v040-20261002-170437`); model-free checks pass,
  including the `cross-llm-claude` picker and preflight.

## Release gate (v0.4.0)

Do not tag until review findings R01–R06
([REVIEW-2026-10-01](../v0.3.1-fixes/REVIEW-2026-10-01.md)) are fixed as their
own sub-project. Until then, avoid `--gc --apply` (especially with
`--include-previous`) on repositories with retained delivery work.

Open evidence gaps: sandboxed Codex lead (canary ran `danger-full-access`),
live POSIX/macOS, live mid-process interruption.
