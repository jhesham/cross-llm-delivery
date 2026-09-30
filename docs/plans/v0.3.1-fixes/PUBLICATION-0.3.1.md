# 0.3.1 publication — 2026-10-01

**Published:** [Cross-LLM Delivery v0.3.1](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.3.1),
stable (not draft/prerelease), marked Latest. Annotated tag `v0.3.1` resolves to
`a464f777f5ce99aa33c35fc6dbc8f17712d17858`.

## Promotion and verification

- Working branch `refactor/codex-support` at `5089a9f` (branch CI for the
  engine source `aa20d1b`: [run 36726451382](https://github.com/jhesham/cross-llm-delivery/actions/runs/36726451382),
  four jobs green; `5089a9f` adds only the README version pointer).
- Checked promotion with `python -m generator.release sync --source-branch refactor/codex-support --no-skills`:
  full local suite passed, bundles regenerated, normal fast-forward of
  `public/main` from `908606f` to `a464f77` ("release: v0.3.1").
- [Exact main CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/36734138777)
  passed Windows/Ubuntu × Python 3.11/3.14; CodeQL on `a464f77` passed.

## Published assets

Built from a clean checkout of `a464f77` with the v0.3.0 assembler
(`.cld/publication-0.3.1/assemble_release.py` → `.cld/t20b/assemble.py`);
Python 3.13.13, pip 26.0.1, setuptools 82.0.1. The isolated wheel passes
`python -I -S` outside the checkout (four providers, no optional dependencies,
exact `+fast` parsing, CLI help); four bundle ZIPs rebuilt identically.
All nine release assets were downloaded back and match local SHA-256.

| File | SHA-256 |
|---|---|
| `source.zip` | `06707ee3faefd3a8dd819a692ea62fdeaf2dafb5e9e6f27020b4f3d0645531a3` |
| `cld-0.3.1-py3-none-any.whl` | `122cecf048116e8b1e31a51a4de99d3333a00fd092c72eb084b7d7eb54d4cfe7` |
| `cld-0.3.1.tar.gz` | `bf41f284c02ebd41e4ad7f7902a6b3e3692349f98fd0523875fd2b8ad54435d3` |
| `claude-skills.zip` | `5b2bb0bf1f80ec8d3b2ebbb339e8afded05ac67a6a4448ffc0df8e1dc3297144` |
| `codex-skills.zip` | `e4f4f9ab8c7b5ac515dfa88bf54400381e29a537e7635377e0f192f1550e48b4` |
| `claude-plugins.zip` | `deeecd8b1131d6660cf28dd27f9b42c809c76dcbf9dda42f91166cc2c7414fcf` |
| `codex-plugins.zip` | `875bd89d2da48d2fc4ff394dd50efb4f4e1157f943bf0ea8887123fd78668027` |

`manifest.json` and `SHA256SUMS.txt` were uploaded and verified as well.
Local files: `dist/release-v0.3.1/`; evidence: `.cld/publication-0.3.1/`.

## Installation and follow-up

- The four global Claude standalone skills were installed from the `a464f77`
  bundles after a verified backup to
  `~/.claude/skill-backups/v031-20261001-013624`; installed files match the
  generated sources. Model-free checks passed on each installed driver (help
  lists `--gc`, demo-plan JSON dry-run, `--gc` preview, Codex picker with zero
  dispatches). Restart the host to load them.
- Issue #12 closed; roadmap #14 updated (v0.3.1 shipped; Claude Code executor next).
- No provider/model calls during publication. Dogfood usage for the fixes is in
  [EVIDENCE.md](EVIDENCE.md).

Live POSIX/macOS, live Claude-lead execution and fast-tier service remain
unverified; publication does not expand evidence.
