# Turning a superpowers plan into a CLD plan

Use this when a lead has planned with superpowers (brainstorming → spec → writing-plans) and wants the
build done by CLD executors. The lead keeps the thinking: design, contracts and tests, review and
integration. The executor implements the slices. Committed tests decide acceptance.

## Mapping

| Superpowers plan | CLD plan |
|---|---|
| A task | One `## SLICE: <id>` block |
| The task's test file | `acceptance_test_path`, committed failing before dispatch |
| The task's "Files: create/modify" list | `files`, the writable allowlist (tests stay outside it) |
| Task ordering and "Consumes" from earlier tasks | `deps` |
| Global Constraints | Repeated in each slice `brief`, or committed as `protected_inputs` |
| Task size or difficulty | Optional `complexity` (`easy`, `standard` or `complex`) |
| Executor chosen for the build | `--executor` (build default) or a per-slice `executor` |

### A task with no test

A task with no test is not a slice: the lead either does it directly (docs, configuration,
regeneration) or writes a failing test for it first.

## Steps

1. **Write the tests.** For each task, write its test from the plan's test step and commit it.
   - Each test must fail at baseline by **AssertionError**, not ImportError or a collection error.
   - Resolve new names lazily inside the test, for example
     `getattr(importlib.import_module(...), name, None)` followed by an assertion, so a missing
     module fails as an assertion.
2. **Write the slices.** Write one `## SLICE:` block per task.
   - **`brief`:** a single line holding the signature, file and decisive values from the task's
     Interfaces block.
   - **`files`:** exactly the task's create/modify list.
   - **`deps`:** the tasks whose "Produces" this task consumes.
3. **Choose the integration selector.** A layer is a set of slices whose dependencies are
   already integrated.
   - The selector is **one** path (a test file or directory), optionally with `-k "<expression>"`.
     A list of several files is not accepted.
   - It is **frozen for the build** the first time it is used, and must pass after **every** layer.
     So put each build's tests under one directory, and exclude a later layer's still-red tests with
     `-k "not <module>"` until that layer lands. Alternatively, run a later layer as its own build.
   - `-k` matches substrings of test and module names, so check what a filter selects
     (`pytest --collect-only -q <selector>`) before integrating.
   - Run neighbouring existing tests that the slices' files touch yourself after integrating, so
     regressions surface before CI.
4. **Run.** Preview with `--dry-run`, then `--step` one layer at a time, reviewing each candidate.
   Then `--integrate --integration-tests <selector>` before the next layer.

## Splitting and merging

- **Split** a task that writes two unrelated files, or whose test checks two independent behaviours,
  into separate slices with their own tests.
- **Merge** tasks that must change the same file in the same layer: two slices cannot both own a file
  at once.
- Keep a slice small enough that its brief fits on one line and its test names the exact behaviour.

## Example

A lead (for example `claude-opus-5-5` at medium effort) brainstorms a feature with superpowers,
approves the spec, and writes a plan with three tasks:
- `parse_config` in `src/app/config.py`;
- `validate_config` in `src/app/validate.py`, consuming `parse_config`;
- `load_settings` in `src/app/settings.py`, consuming both.

```text
## SLICE: PARSE
brief: Implement parse_config(text: str) -> dict in src/app/config.py; keys and errors as in tests/app/test_config.py.
files: src/app/config.py
acceptance_test_path: tests/app/test_config.py
deps:

## SLICE: VALIDATE
brief: Implement validate_config(cfg: dict) -> list[str] in src/app/validate.py using parse_config.
files: src/app/validate.py
acceptance_test_path: tests/app/test_validate.py
deps: PARSE

## SLICE: SETTINGS
brief: Implement load_settings(path) -> Settings in src/app/settings.py using parse_config and validate_config.
files: src/app/settings.py
acceptance_test_path: tests/app/test_settings.py
deps: PARSE, VALIDATE
```

The tests live under `tests/app/`, and the build runs with `--executor codex:gpt-6-luna@max+fast`:
1. Layer 1 is PARSE, integrated with `tests/app -k "not test_validate and not test_settings"`. That
   selector is now frozen for the build.
2. Layer 2 is VALIDATE. With the same frozen selector, its own test is checked when CLD accepts the
   slice.
3. Layer 3 is SETTINGS, accepted the same way.
4. Finally, the lead runs `pytest tests/app` across the three layers. For a full-suite integration
   gate, run the later layers as a second build with selector `tests/app`.

The lead reviews each accepted candidate before integrating it.
