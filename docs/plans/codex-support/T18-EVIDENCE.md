# T18 — Checked release automation

Implementation and **59 focused local checks pass**. The checked CI helper verified
[source/test SHA 032cc26 four-job CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/36392139614):
Windows/Ubuntu Python 3.11/3.14 full offline tests and all five artifact gates.
[Clean-checkout previews](T18-PREVIEW.md) changed no local refs or tracked files.
The closing push includes four final edge checks and the relative local-remote
repair; its exact-SHA four-job CI must also pass before handing off or advancing
to T19. Final metadata is retained in `.cld/t18/ci-final-jobs.json`. No public main sync,
release tag, GitHub Release, provider mirror publication or global skill copy has
been executed in this task.

## Contract and implementation

The committed red baseline `eef006b` contains the bounded
[T18 contract](T18-CONTRACT.md), [dogfood plan](T18-DOGFOOD.md), and 30 failing
acceptance cases. The lead implemented the checked release module and thin
PowerShell wrappers after the dogfood attempt failed to produce changes.

`generator.release` checks all native results and reports argv, return code and
output. Source checkout/branch, the sole expected push URL, version consistency,
release tag absence and nonempty literal notes are preconditions. Generators for
both hosts and their complete matching plugin sets are verified before commits.
Only intended files are committed. A detached owned worktree stages the mirror;
normal explicit branch pushes, exact repository/workflow/branch/full-SHA bounded
CI polling, optional checked skills copy and checked cleanup follow in order.
Failure preserves edits/commits and available staging. Per-command Git identity
leaves caller environment and cwd unchanged. Tags name the verified mirror SHA;
release notes use an owned file rather than shell or CLI-body interpolation.

`generator.publish` previews isolated bundle hashes without modifying requested
dist output. Read-only source Git inspection supplies provenance; preview makes
no remote query or publishing mutation. VERSION and pyproject must agree with
the requested version and generated banner. Existing tags are rejected before
generation; existing branch replacement requires explicit expected SHA and
replacement intent. A single atomic push names the branch and only the intended
tag, with an exact force-with-lease when replacement is requested. Failure
retains publisher staging. Windows read-only Git object cleanup is checked.
Both host variants, four provider bundles and --all umbrella previews work.

## Verification

`python -m pytest tests/test_t18_release.py tests/test_publish.py -o addopts= -q`: **59 passed**
on Windows Python 3.13. Real Git operations target disposable local bare repos;
pytest/generators/gh are injected where release workflow sequencing is tested.
Native push/add/commit/tag/generation/test/gh/worktree/CI/copy/cleanup failures
stop later steps. Queue/no-run/malformed/cancelled/failed CI results cannot
produce success. Guarded replacement succeeds only for the exact inspected SHA,
retains unrelated tags, and a concurrent update causes atomic branch/tag
rejection. Successful release fixture tags the actual mirror commit and reads
literal multiline notes with shell-like text from a file. Source TOML sections
and nonstandard Unreleased whitespace are preserved correctly. PowerShell
wrappers propagate Python failure in paths with spaces.

Lead review corrected two fixture defects after dogfood: fake generation now
actually changes a plugin so add/commit failure checks execute; existing mirror
clones explicitly select main instead of depending on a bare repo's default HEAD.
The Windows cleanup defect found in the first run was repaired and reverified.
Final review fixed relative local remote paths: resolve them against the source
root before preflight/staging so cwd changes cannot redirect a push. Real-Git
checks also prove unchanged mirrors still push/check exact CI, fetch failure
stops before staging, and multiple push URLs are rejected. The relative-path
fixture was rerun after making its version independent of future source bumps
(one passing case).

## Dogfood and usage

Exact executor: `opencode:opencode/kimi-k3` (installed model listing confirmed).
Run `901f496d00b54ceea68595cb6c6a6b88`, ledger `.cld/t18/ledger.json`, retained
worktree `.cld/worktrees/T18-901f496d-b1b727ef38244ea5b35c35a569aeeaeb`.
Validation passed with 11,113 input + 649 output + 48,640 cached-read tokens =
**60,535 reported provider tokens**, **USD 0.059661**. Production timed out after
**600.004988 seconds**, with empty stdout/stderr and **no file changes**. No
candidate was accepted. Production usage/cost are **unknown**, not zero; the
reported validation values are only known lower bounds for the combined spend.
Two admitted attempts including validation exhausted this run's attempt budget;
there was no third call, silent model substitution or extra canary. Lead token
counters are unavailable. The original 8–12k lead estimate was exceeded by the
timeout, implementation review and expanded failure/race checks; avoid broad
600-second briefs for later dogfood tasks.

## Limits and recovery

No live release/publish/copy result is claimed. Branch CI verifies Windows/Ubuntu
Python 3.11/3.14 and generators offline; macOS and live POSIX provider evidence
remain unchanged. The optional historical Claude skills copy merges generated
files, preserving extra destination files; preview exposes the destination and
--no-skills disables it. On a failure after a push, inspect the exact remote refs,
retained worktree/notes path and source commit before retrying. There is no
rollback of published refs or generic deletion of source changes. A failed
release may require manual continuation from its retained version commit; the
clean-checkout precondition deliberately prevents blindly repeating a bump.
