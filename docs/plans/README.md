# Development records

The files under `docs/plans/` are historical development records: implementation
plans, task contracts, review findings, defect registers, handoffs and evidence
captured while the project was being built. They are kept for transparency and
to explain why the code looks the way it does. They are not product
documentation.

## Limits

- Records describe the project at the time they were written. Behaviour, flags,
  provider support and model IDs may since have changed.
- Commit SHAs, branch names and tags quoted in records may no longer resolve, or
  may point at different content, after the Git history was rewritten.
- Commands are recorded as they were run during development. They may be stale,
  may depend on local state that no longer exists, and should not be copied as
  current instructions.
- Checked boxes and "passed" statements record what was verified then, not a
  guarantee about the current release.

## Placeholders

Machine-specific details were replaced with placeholders. Substitute your own
values when reading a recorded command:

| Placeholder | Meaning |
|---|---|
| `<repo>` | Absolute path to a local checkout of this repository |
| `<home>` | The current user's profile/home directory |
| `<host>` | A local machine name |
| `<local-review-artifacts>` | A local directory of review and probe files that was never published |
| `<system-drive>` | The Windows system drive letter, for example `C:` |
| `<author-email>` | The email address in a commit trailer or author line |

## Current guidance

For current installation, usage and limitations, use:

- [README](../../README.md)
- [Installation](../../INSTALL.md)
- [Known issues](../../KNOWN-ISSUES.md)
