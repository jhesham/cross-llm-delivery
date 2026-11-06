### Antigravity (`agy`) executor

The recorded Antigravity catalog describes subscription/quota models. Actual
per-call usage/cost may be unavailable; do not infer zero from the subscription.
It exposes Gemini, Claude and GPT-OSS
models -- select with `--executor "antigravity:<label>"`, e.g. `antigravity:Claude Opus 5.5 (High)`.
The default workhorse is `antigravity:Gemini 4 Argon (High)`.
Slugs such as `antigravity:gemini-4-argon-high` also work.
Run `agy models` in any terminal to list current models, including Gemini 3.8
Flash, Gemini 4 Argon, Claude Sonnet 5.5, Claude Opus 5.5 and GPT-OSS 120B.

Windows note: `agy` writes the model reply to a transcript file under `~/.gemini/antigravity-cli/`
using a POSIX path. On Windows the executor uses a working directory on
`SystemDrive` so the transcript path resolves; on POSIX it uses the native home
directory. An explicit home override is preserved. It identifies the dispatch's
conversation from the CLI log and reads that conversation's transcript under
the selected home. See `references/provider-setup.md` for path details.
Authenticate once interactively (`agy`, browser login) before running headless builds.
