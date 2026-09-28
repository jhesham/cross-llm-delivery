### Antigravity (`agy`) executor

The recorded Antigravity catalog describes subscription/quota models. Actual
per-call usage/cost may be unavailable; do not infer zero from the subscription.
It exposes Gemini, Claude and GPT-OSS
models -- select with `--executor "antigravity:<label>"`, e.g. `antigravity:Claude Opus 4.6 (Thinking)`.
The default workhorse is `antigravity:Gemini 3.1 Pro (High)`.

Windows note: `agy` writes the model reply to a transcript file under `~/.gemini/antigravity-cli/`
using a POSIX path, so the executor runs the CLI with its working directory on the C: drive and reads
the reply from the latest transcript. Authenticate once interactively (`agy`, browser login) before
running headless builds.
