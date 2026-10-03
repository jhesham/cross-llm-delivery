# N07 — native OpenCode launcher contract

Implement only native discovery/launch consistency. Acceptance is offline: fake
processes plus a local Python native child, never another model/provider call.

- Add cld_providers/opencode/launcher.py with resolve_opencode_command(env=None,
  which=shutil.which, os_name=None), returning shared NativeCommand and raising
  NativeCliError. Reuse cld.native_cli.resolve_native, not a new shell launcher.
- Priority: explicit absolute existing OPENCODE_CLI_CMD, native opencode.exe on
  Windows PATH, then the verified npm postinstall target behind opencode.cmd:
  <shim-dir>/node_modules/opencode-ai/bin/opencode.exe. POSIX uses native PATH
  discovery through the shared resolver. Do not guess optional CPU/AVX package
  selection when that postinstall target is missing; fail with override guidance.
- The lead inspected installed opencode-ai 1.18.29 package.json/postinstall.mjs.
  Postinstall selects platform/architecture/CPU support before linking/copying
  bin/opencode.exe. That output is the supported npm target for this slice.
- Refuse Windows explicit .cmd/.bat shell shim overrides in the shared resolver,
  even if the file exists. Missing/invalid overrides must not silently fall back.
- Export/import resolve_opencode_command in provider.py. _oc_cmd exposes its
  selected native path. Register cli_invocation and launch_problem using the
  same resolver, following the existing Codex/Claude provider pattern.
- Keep logical 'opencode' at the argv boundary for dispatch, model discovery and
  account stats. The production _default_runner resolves/rewrites that prefix
  through resolved_runner; leave unrelated Python/Git commands alone. Preserve
  the selected command's env under caller overlays, without mutating input argv.
- Preserve injected runner(argv, cwd) compatibility without requiring an installed
  CLI. Native resolution failures stop production with missing_binary before any
  inference/diff capture. Discovery returns [] and account stats empty on failure.
- Keep exact model/variant, long/multiline Unicode prompt argv, --dir, --format
  json, fresh --port, recursion guard/child marker, timeouts, cancellation and
  artifact options unchanged. No tests, generated files, Git mutations, installs,
  global settings, other model calls, F01 classification or N08 cwd changes.
- Update provider setup notes to describe priority and fail-closed shim behavior.

Run only tests/test_n07_opencode_native.py with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.
If Windows sandbox/test temporary-directory access fails, report it and stop
retrying. Do not create alternative temp directories, broaden grants, install
tools, or weaken tests. The lead independently verifies captured source.
