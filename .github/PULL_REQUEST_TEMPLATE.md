## What & why

<!-- One or two sentences. Link the issue if there is one. -->

## Checklist

- [ ] **Failing test first** — behavior changes come with a test that pinned the old behavior red
      (this project's core convention; see CONTRIBUTING.md).
- [ ] `python -m pytest -q` green locally (no API keys or executor CLIs needed for the default run).
- [ ] If judging/verification logic changed: it rests on real signals (exit codes, diffs, file
      existence) — never on parsing prose or trusting a model's self-report.
- [ ] `dist/` and `plugins/` untouched by hand (both are generated).
