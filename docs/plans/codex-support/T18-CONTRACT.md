# T18 checked release automation contract

Implement only `generator/release.py`, `generator/publish.py`, `release.ps1`, and
`sync-public.ps1`. Lead-owned acceptance is `tests/test_t18_release.py` plus the
existing `tests/test_publish.py`. Do not edit tests, publish anything, invoke
providers/CLD recursively, commit, push, or run the full suite. Use only the
focused tests, fake commands and local bare remotes. Finish promptly.

## Shared checked operations

Create `generator.release` (standard library only). `CommandError(RuntimeError)`
and `checked(argv, cwd, *, runner=None, ok_codes=(0,))` must preserve the exact
failed command, return code and diagnostic output in errors. The injectable
runner `(argv, cwd) -> (rc, combined_output)` defaults to subprocess with UTF-8
decoding. Every native operation must go through `checked`; no unchecked Git,
generation, pytest, gh, copy or cleanup command may lead to success.

`wait_for_ci(*, repo, workflow, branch, sha, cwd, runner=None, timeout=3600,
interval=10, clock=time.monotonic, sleep=time.sleep)` polls `gh run list --repo
<repo> --workflow <workflow> --branch <branch> --commit <full-sha> --json
databaseId,headSha,headBranch,workflowName,status,conclusion,url`. Independently
filter returned rows by exact SHA, branch and expected workflow (`CI` when
workflow is `ci.yml`, otherwise the supplied name). Never watch an unrelated
latest run. Use bounded polling for queue delay/no matching run; fail on
malformed JSON, cancelled/failing matching run or deadline. Return the matching
successful row. Do not use unbounded `gh run watch`.

## Sync and release APIs

Expose `sync_public(repo_root, *, message='sync: mirror master fixes to public',
source_branch='master', remote='public', remote_url='https://github.com/jhesham/cross-llm-delivery.git',
github_repo='jhesham/cross-llm-delivery', target_branch='main', workflow='ci.yml',
skip_tests=False, no_ci=False, no_skills=False, skills_root=None, dry_run=False,
runner=None, ci_timeout=3600)` and `release_version(repo_root, version, **same
target options)`. A clean source checkout, intended current source branch,
expected remote URL, single-line safe ref names, matching VERSION/pyproject,
valid X.Y.Z and absent local/remote release tag are preconditions. Reject
invalid requests before changing files. Dry-run is read-only (no generation,
worktree, commits, tags, pushes, copies, gh release or source edits); read-only
Git inspection is allowed. Return a reviewable dict with source SHA/branch,
remote URL, target ref, version/tag, exact destination/artifact paths and
ordered operations (`actions`). Public result keys: `source_sha`, `target_ref`,
`remote_url`, `version`, release `tag`, execution `pushed_sha`. Never imply a
dry-run grants execute authorization.

Sync checks pytest unless skipped; generation of both host variants and Claude
plugins must be checked. Validate every generated plugin manifest version
against VERSION. Commit only generated tracked plugins when changed, with
per-command `git -c user.name=... -c user.email=...`; do not mutate environment
or identity settings. Read/fetch exact remote target state and mirror the
committed source tree in an owned detached Git worktree under
`<repo>/.cld/release/`. Exclude SHIP-PLAN.md, release.ps1, sync-public.ps1 like
the existing mirror contract. Use a normal explicit `HEAD:refs/heads/<branch>`
push: no force. An unchanged snapshot still requires push/CI verification
rather than an early success. Use full pushed SHA for CI. A staging/push/CI
failure retains the worktree and commit and reports its path; no generic
checkout/reset/remove-force/prune rollback. On success remove only the owned
clean worktree, after validating its absolute containment. Preserve caller
cwd/environment. Check optional skills copy results (robocopy 0–7 are success
on Windows; errors on other platforms also fail). Default skills destination
may retain historical `<home>/.claude/skills`, but preview must show it and
tests always select disposable paths or no_skills.

Release extracts nonempty Unreleased notes, validates all preconditions first,
then bumps VERSION/pyproject/changelog, tests, regenerates and verifies
versions, commits only intended version/changelog/plugin files, syncs without
repeating tests, waits exact CI, tags the actual mirrored commit, pushes that
explicit tag, and calls `gh release create ... --repo ... --notes-file <file>`.
Stop on every failure. Preserve staged/version changes on failure rather than
discarding them. No `dist/` staging, broad `git add -A` on source, blind cleanup,
global identity edits or success output after a failed operation.

CLI: `python -m generator.release release --version X.Y.Z` and `sync` with
`--repo-root`, `--source-branch`, `--remote`, `--remote-url`, `--github-repo`,
`--target-branch`, `--workflow`, `--ci-timeout`, `--dry-run`, sync `--message`,
`--skip-tests`, `--no-ci`, `--no-skills`, `--skills-root`. Return JSON plan/result
on success; useful error and nonzero on failure. PowerShell scripts retain
Version/DryRun or Message/SkipTests/NoCI/NoSkills, add matching target options,
and forward to this module. Check Python's native result and propagate it;
restore location in finally, no environment edits or own release mutations.

## Bundle mirror publishing

Preserve `load_publish_targets`, `publish_one`, `publish_umbrella` and CLI.
Add `target_branch='main'`, `expected_sha=None`, `replace_history=False`,
`host='claude-code'`. Validate version matches source VERSION/pyproject and
generated artifact before executing; fail before generation for mismatched
version/invalid target. Preview builds only in a temporary owned directory
(not requested dist_root), makes no Git/network calls or persistent writes,
and reports `target_ref`, `tag`, `expected_sha`, `replace_history`, `file_hashes`
(relative path to SHA-256 mapping), artifact paths and
ordered argv actions. `--all` preview must include umbrella if execution would.

Execution queries exact remote branch and release tag before generation.
An existing release tag is rejected. An existing branch may be replaced only
with `replace_history=True` AND an explicit matching 40/64-hex `expected_sha`;
empty branch can use normal creation without replacement. Reject stale
expectation before publishing. Push branch and only the intended version tag
in one `git push --atomic`, with explicit refspecs and an exact
`--force-with-lease=refs/heads/<branch>:<expected-sha>` for approved replacement.
No plain `--force`, ambiguous HEAD remote destination, or `--tags`. Every
command failure stops later operations, and CLI catches/returns nonzero
without a success claim. Keep per-provider output names and support four
providers/both host generation. Do not run any real public publish operation.
