# N08 — native Antigravity cwd contract

Fix only the POSIX cwd defect and its diagnostics/documentation.

- `_dispatch_cwd()` must return `str(Path.home())` on POSIX, without applying
  SystemDrive or constructing a Windows drive path. Keep the existing Windows
  SystemDrive case-insensitive comparison and cross-drive `/Users` transcript
  workaround. Preserve explicit constructor `home` overrides.
- Production dispatch must still run from the selected home, pass the worktree
  with `--add-dir`, preserve exact model, timeout/cancel/artifact options and the
  recursion marker, and read transcripts from that same home. Legacy two-argument
  injected runners remain compatible. No change to command selection or prompts.
- Make the missing-transcript hint accurate on POSIX; keep useful Windows
  SystemDrive guidance. Do not claim live POSIX/macOS provider verification.
- Update antigravity/setup.md with the platform distinction, explicit home
  semantics and verification limit. The lead owns tests and generated output.
- Allowed files: engine/cld_providers/antigravity/provider.py and setup.md only.
  No tests, Git mutations, installs, global settings, other providers/model calls,
  F01 changes, OS-wide `os.name` monkeypatch or unrelated refactoring.

Run only tests/test_n08_antigravity_cwd.py with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.
If Windows restricted-token pytest/temp access fails, report it and stop retrying.
Do not create alternate temp roots, broaden grants or weaken tests. Independent
CLD acceptance judges captured source. The native POSIX subprocess case is skipped
on Windows and must pass on Ubuntu CI before closure.
