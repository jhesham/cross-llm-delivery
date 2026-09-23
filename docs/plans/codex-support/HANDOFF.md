# Current handoff

Updated 2026-09-23. **T01–T12 and M1–M3 complete.** Stop for the user's explicit token-availability
confirmation before T13. Branch `refactor/codex-support`, remote `public`; final T12 code/test
head `3b1c0b9`, closing docs follow it. No main merge, release or user-global installation.

T12A added standalone Codex skill generation under `dist/codex/` for antigravity, cursor and
opencode. T12B added verified `agents/openai.yaml` metadata, an identical shared workflow
reference in both hosts, corrected Claude bundle driver paths, and portable Codex plugin packages
under ignored `dist/plugins/codex/` by default. The no-argument Claude plugin generator retains
its original `plugins/cross-llm-*` layout and names. Six host/provider bundles run isolated JSON
previews from another cwd. [T12A evidence](T12A-EVIDENCE.md); [T12B evidence](T12B-EVIDENCE.md).

T12B used one exact `opencode/kimi-k3` validation probe and one production attempt, no fallback.
Reported combined usage was 1,794,375 tokens and USD 1.0957002; the attempt exceeded its
1,500,000-token reservation, which was not a provider cap. CLD accepted commit `3553732` and
independently integrated it at `892bcc0`; branch cherry-pick `aeea9ce`. Lead review fixed Codex
plugin default output (`d7b591e`) and a pre-existing Ubuntu cancellation-test timing race
(`3b1c0b9`). T12A's separate timeout usage remains unknown with lower bounds in its evidence.
Retain both ignored `.cld/t12*-dogfood/` evidence trees.

Final [Windows/Ubuntu CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/35849789785)
passed full tests and all three smoke steps on each OS: Claude bundles, Codex bundles, Codex
plugin packaging. Local 38-case focused generator suite and full offline suite passed; the
four recovery tests were rerun after the final timing-fixture edit. This validates generation
and packaging only. Actual Codex/Claude host discovery and installation are T13/T14; wheel
coverage is T17.

When the user confirms tokens for T13, read [T13's plan](04-CODEX-HOST.md#t13--codex-installation-and-discovery)
and the tracker, then commit a bounded contract and red acceptance before any dogfood dispatch.
Verify current official Codex installation/discovery paths and keep all installs disposable until
the user selects a real target. Stop again after T13 for the next token checkpoint.
