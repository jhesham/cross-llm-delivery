## SLICE: GATEWAY3
brief: In engine/cld_providers/claude/preflight.py resolve_gateway, gateway mode must give managed settings priority over the inherited environment, because Claude settings override inherited environment values: when the managed settings file routes through a gateway (ANTHROPIC_BASE_URL in its "env"), return (managed host, None) even if the environment also sets ANTHROPIC_BASE_URL; otherwise keep today's environment rules (URL plus ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY, problem naming ANTHROPIC_AUTH_TOKEN when the credential is missing) and today's user-settings-only refusal. Subscription mode is unchanged. Problems never contain setting values.
files: engine/cld_providers/claude/preflight.py
acceptance_test_path: tests/v051/test_review2_gateway.py
deps:
complexity: easy

## SLICE: INSTALLER3
brief: In generator/install_codex.py _install, limit the copy fallback to fresh installs. When stage.replace(target) raises OSError: if this run moved a previous installation to the backup (updating), immediately rename the backup back to the target (backup.replace(target)), remove the stage, and raise Reject (or an OSError subclass already used by the installer) with a message that the update could not be published because the skills folder is in use, the previous installation was kept, and to close running Codex sessions and retry; never copy over or into the target when updating. If the restoring rename also fails, re-raise with a note naming the backup path and the target. For a fresh install (no backup), keep the current exclusive-create copy fallback, its ownership verification, and its clean-up of only what this run created. Original errors stay the raised error with notes attached for any clean-up problem.
files: generator/install_codex.py
acceptance_test_path: tests/v051/test_installer_fallback.py
deps:
executor: codex:gpt-6.1-sol@high
complexity: standard
