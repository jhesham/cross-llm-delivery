### Antigravity (`agy`) executor

Antigravity is a flat-rate plan (quota-based; $0 marginal). It exposes Gemini, Claude and GPT-OSS
models -- select with `--executor "antigravity:<label>"`, e.g. `antigravity:Claude Opus 4.6 (Thinking)`.
The default workhorse is `antigravity:Gemini 3.1 Pro (High)`.

Windows note: `agy` writes the model reply to a transcript file under `~/.gemini/antigravity-cli/`
using a POSIX path, so the executor runs the CLI with its working directory on the C: drive and reads
the reply from the latest transcript. Authenticate once interactively (`agy`, browser login) before
running headless builds.
