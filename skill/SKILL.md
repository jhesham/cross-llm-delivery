---
name: cross-llm-delivery (DEPRECATED — do not install this file)
description: >-
  DO NOT INSTALL THIS FILE. This is a deprecation stub, not a skill. The unified
  multi-provider skill was replaced by per-provider skills generated from this
  monorepo (cross-llm-antigravity, cross-llm-opencode, cross-llm-cursor, …). Run the
  generator and install one of those. See INSTALL.md + README.md.
---

# ⛔ DO NOT INSTALL THIS FILE — run the generator

**This is a deprecation stub, not an installable skill.** Copying this `skill/` folder into
`~/.claude/skills/` will NOT work — it has no vendored engine.

To get a real, self-contained skill:

```
pwsh ./rebuild-skills.ps1          # or:  python generator/build_skill.py --all
```

then copy ONE generated `dist/cross-llm-<provider>/` folder into `~/.claude/skills/`.
Full steps (fresh machine, executor install + auth): **[INSTALL.md](../INSTALL.md)**.

Live providers: **antigravity** (default workhorse), **opencode**, **cursor**, **composer**.

## Where the real content lives (for maintainers)

- `skill/SKILL.template.md` — the provider-agnostic skill body the generator fills
  (`{{PROVIDER_NAME}}` / `{{PROVIDER_FRAGMENT}}` / `{{SETUP}}` / `{{BANNER}}` placeholders).
- `engine/cld_providers/<provider>/SKILL.fragment.md` — each provider's slice of the docs.
- `skill/scripts/run_delivery.py`, `skill/references/` — live generator inputs (vendored into
  every generated skill; do not edit copies under `dist/`).

Nothing in the engine, tests, or generator reads this file — it exists only so a stale link
finds this explanation.
