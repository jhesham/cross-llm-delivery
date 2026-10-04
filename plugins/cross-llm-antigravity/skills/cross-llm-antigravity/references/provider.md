### Antigravity (`agy`) executor

The recorded Antigravity catalog describes subscription/quota models. Actual
per-call usage/cost may be unavailable; do not infer zero from the subscription.
It exposes Gemini, Claude and GPT-OSS
models -- select with `--executor "antigravity:<label>"`, e.g. `antigravity:Claude Opus 4.6 (Thinking)`.
The default workhorse is `antigravity:Gemini 3.1 Pro (High)`.

Windows note: `agy` writes the model reply to a transcript file under `~/.gemini/antigravity-cli/`
using a POSIX path. On Windows the executor uses a working directory on
`SystemDrive` so the transcript path resolves; on POSIX it uses the native home
directory. An explicit home override is preserved. It identifies the dispatch's
conversation from the CLI log and reads that conversation's transcript under
the selected home. See `references/provider-setup.md` for path details.
Authenticate once interactively (`agy`, browser login) before running headless builds.
