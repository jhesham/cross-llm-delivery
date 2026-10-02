# 0.4.0 publication — 2026-10-03

**Published:** [Cross-LLM Delivery v0.4.0](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.4.0),
stable (not draft/prerelease), marked Latest. Annotated tag `v0.4.0` resolves to
`429b9d05cd746865e0facd04874189ee54d1c8a4`.

Contents: the Claude Code executor ([claude-executor](../claude-executor/HANDOFF.md)) and
review fixes R01–R07 ([SPEC](SPEC.md), [PLAN](PLAN.md)).

## Promotion and verification

- Working branch `refactor/codex-support` at `b8d68e0` (0.4.0 bump). Branch CI for the
  fixes at `e707c55`: [run 37006119339](https://github.com/jhesham/cross-llm-delivery/actions/runs/37006119339),
  four jobs green.
- Checked promotion with `python -m generator.release sync --source-branch refactor/codex-support --no-skills`:
  full local suite passed, bundles regenerated, normal fast-forward of `public/main`
  from `a464f77` to `429b9d0`. The `main` commit carries the tool's default message
  ("sync: mirror master fixes to public") because `--message` was not passed; content is
  the mirrored `b8d68e0` tree.
- [Exact main CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/37022369621)
  passed Windows/Ubuntu × Python 3.11/3.14.

## Published assets

Built from a clean checkout of `429b9d0` with the v0.3.0 assembler adapted for five
providers (`.cld/publication-0.4.0/assemble_core.py` via `assemble_release.py`). Codex
release plugins were generated with `--out-root dist/release-plugins`; committed Claude
plugins were used as-is. The isolated wheel passes `python -I -S` outside the checkout
(five providers, no optional dependencies, CLI help); four bundle ZIPs rebuilt
identically. All nine release assets were downloaded back and match local SHA-256.

| File | SHA-256 |
|---|---|
| `source.zip` | `fbaf79bc5b99f6f983192c172e250af4a47e1fce634a07a7e413a8d0bfe01ed8` |
| `cld-0.4.0-py3-none-any.whl` | `397baf195e9a9161aabd1e60874f9f71bebe1b8bfb0036db3c8010b307e1dca3` |
| `cld-0.4.0.tar.gz` | `b03e1cca2688104eb43748a70387f06b80cdc0476a40d6a3961fc93dc653914c` |
| `claude-skills.zip` | `1cc9636c9d0d4f58e4811c2119e14c33a1e33f361e300a2ce1d033e650922583` |
| `codex-skills.zip` | `b384426edf73203cf5e06e09a9a1a2a595de0910c4c3ea9a3845ec08b76e4e9e` |
| `claude-plugins.zip` | `1f392bd45f92a1812cf97734e9ef22d5dfa85aada86f9553f06010a5d6ecc7af` |
| `codex-plugins.zip` | `188c10ccb42313911832f1c0d66554e243da04edd2b2c3451d5936ad419e16b7` |

`manifest.json` and `SHA256SUMS.txt` were uploaded and verified as well
(`SHA256SUMS.txt` has CRLF line endings, as in 0.3.1; strip `\r` before `sha256sum -c`).
Local files: `dist/release-v0.4.0/`; evidence: `.cld/publication-0.4.0/`.

## Installation and follow-up

- The five global Claude standalone skills were installed from the `429b9d0` bundles
  after a verified backup to `~/.claude/skill-backups/v040-release-20261003-024307`;
  installed files match the generated sources. Model-free checks passed on each
  installed driver (help lists `--gc`, demo-plan JSON dry-run, `--gc` preview) and the
  Claude picker's `list_models.py --json`. Restart the host to load them.
- Roadmap #14 updated (v0.4.0 shipped; Claude executor removed from near-term).
- No provider/model calls during publication.

Live POSIX/macOS, a sandboxed Codex lead and live mid-process interruption remain
unverified; publication does not expand evidence.
