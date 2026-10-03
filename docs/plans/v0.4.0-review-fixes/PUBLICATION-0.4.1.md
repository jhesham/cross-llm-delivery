# 0.4.1 publication — 2026-10-03

**Published:** [Cross-LLM Delivery v0.4.1](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.4.1),
stable, marked Latest. Annotated tag `v0.4.1` resolves to `7372fdb37f54044a63ad061024da3945280540ff`.

Contents: re-review fixes N01 (`eb370a4`) and N02 (`4ffbab3`) by the Claude Code lead, N03
(`7ff0f2d`) by the Codex lead, developed concurrently on `refactor/codex-support`
([review](REVIEW-2026-10-03.md), [N03 record](N03-OPENCODE-INLINE-FIX.md)).

## Promotion and verification

- Branch `refactor/codex-support` at `f019689` (0.4.1 prep); branch CI
  [37095765709](https://github.com/jhesham/cross-llm-delivery/actions/runs/37095765709) green.
- Local full suite: 1212 passed; the other 14 failed only because the version was bumped mid-run
  without regenerating stamps, and all 14 pass after regeneration and on the committed state.
- Checked promotion (`generator.release sync --message "release: v0.4.1"`): fast-forward of
  `public/main` from `429b9d0` to `7372fdb`.
  [Exact main CI 37098747062](https://github.com/jhesham/cross-llm-delivery/actions/runs/37098747062)
  passed Windows/Ubuntu × Python 3.11/3.14.

## Published assets

Built from a clean checkout of `7372fdb` with the five-provider assembler
(`.cld/publication-0.4.1/`); isolated wheel passes `python -I -S` (five providers); bundle ZIPs
rebuilt identically. All nine assets downloaded back and verified; `SHA256SUMS.txt` now has LF
endings, so `sha256sum -c SHA256SUMS.txt` works directly.

| File | SHA-256 |
|---|---|
| `source.zip` | `43bfb5f85e95d57332f0d527ea0f7b9e2750cc9d9f967c4eef857627d00605e1` |
| `cld-0.4.1-py3-none-any.whl` | `1fec1a632c9aa60a8c4f09bdbf285c92d8e27c8a8b2f9efe78a1dd2047d334c5` |
| `cld-0.4.1.tar.gz` | `1078b1d2b2425a15d1e52404d9488c8bfca1049bd2409a32ad64ab20294fab4f` |
| `claude-skills.zip` | `a4f1176b705489b5ba7f6ec26327ea67041a0ace7aac0f5222e23caf5d34754e` |
| `codex-skills.zip` | `fb8bc865da50bf17e20ce3de8dd34911b25d8004e4aa27a36e905d6481864589` |
| `claude-plugins.zip` | `0bb78cc1e7aabfa027be78ebb2e81da5380b5bd2dfd02bd04c8bf1a66b0b0945` |
| `codex-plugins.zip` | `1c810b021ca534a5a6290bbb86a5b3499e1b6a8415d14c9718cf1d3748112c5b` |

## Installation

Five global Claude skills installed from `7372fdb` after backup to
`~/.claude/skill-backups/v041-release-20261003-153206`; model-free checks pass (demo-plan
dry-run, `--gc` preview, Claude picker). No provider/model calls during publication.
