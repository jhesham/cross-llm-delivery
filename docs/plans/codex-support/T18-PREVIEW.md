# T18 read-only release preview

Observed 2026-09-28 at source `032cc260cb24d5a88359e15874ed285dbe791635`. This is a proposed
0.3.0 preview for inspection only; no version bump, tag, main push, release or
skills copy was executed. T20 still owns the final release candidate/version.

| Field | Inspected value |
|---|---|
| Source branch | `refactor/codex-support` |
| Remote URL | `https://github.com/jhesham/cross-llm-delivery.git` |
| Target ref | `refs/heads/main` |
| Inspected remote SHA | `67ad2f5815e106d0f2f84bfc9f896807411f81e6` |
| Proposed tag | `v0.3.0` |
| Optional local skills copy | Explicitly disabled for this preview |
| Recovery worktree | `D:\claude_server\cross-llm-delivery\.cld\release\stage-8587b4c36ff943f8b89271f0b9d6bf4f` (planned, not created) |

## Ordered operations

1. `bump VERSION, pyproject and changelog`
2. `pytest`
3. `generate and verify versions`
4. `commit VERSION pyproject.toml CHANGELOG.md plugins only`
5. `sync normal branch push and exact-SHA CI`
6. `git tag v0.3.0 <verified-mirror-sha>`
7. `git push public refs/tags/v0.3.0:refs/tags/v0.3.0`
8. `gh release create v0.3.0 --repo jhesham/cross-llm-delivery --verify-tag --notes-file <owned-notes-file>`

The eventual pushed SHA is created by version/plugin and mirror commits and
must pass exact-SHA CI before tagging; the preview does not invent that SHA.
Literal Unreleased notes remain in the JSON preview and are not yet updated for
all Codex work. T20 will prepare final release notes.

## Bundle previews

Both hosts generated isolated per-provider and umbrella previews from
`generator/publish-targets.example.toml`. Its remotes are examples, not approved
publication targets. All four provider bundles are present inside the umbrella.

| Host | Per-provider files | Umbrella files | Tag |
|---|---:|---:|---|
| claude-code | 53 | 217 | `v0.2.0` |
| codex | 52 | 213 | `v0.2.0` |

Full plans, exact paths, commands and bundle file SHA-256 maps are retained in
`.cld/t18/previews/{sync,release,bundles-claude-code,bundles-codex}.json`.
Local `git show-ref` and clean tracked checkout were unchanged before/after.

Reproduce from a clean checkout (read-only remote inspection is allowed):

```powershell
python -m generator.release sync --source-branch refactor/codex-support --dry-run --no-skills
python -m generator.release release --version 0.3.0 --source-branch refactor/codex-support --dry-run --no-skills
python -m generator.publish --all --targets generator/publish-targets.example.toml
python -m generator.publish --all --targets generator/publish-targets.example.toml --host codex
```

Hashes of the locally retained preview JSON (not final release artifacts):

- `bundles-claude-code.json`: `b3a331588ac8fd2b742ef9e04e2c84046af3babcdf0209c2cfd7715048e4674c`
- `bundles-codex.json`: `94477f87a8c3a50c70df4d8380b70f28e93c21c0a97eb2930b8e8b710540a486`
- `release.json`: `1603e3739954a88850b17769c803abe60702c2ef697c93a7421b49c5db04a4e5`
- `sync.json`: `7fb45692be3dc5ef46924523797c1aa000a25540a2b8c0fac7587e07fb9def7c`
