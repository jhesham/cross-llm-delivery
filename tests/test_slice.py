from cld.plan.slice import load_slices, slices_to_markdown

PLAN = """## SLICE: T1
brief: do a
files: src/a.py
acceptance_test_path: tests/test_a.py
deps:

## SLICE: T2
brief: do b
files: src/b.py
acceptance_test_path: tests/test_b.py
executor: opencode:opencode/claude-sonnet-4-6
deps: T1
"""


def test_executor_field_parsed_when_present_else_none():
    s = {x.id: x for x in load_slices(PLAN)}
    assert s["T1"].executor is None
    assert s["T2"].executor == "opencode:opencode/claude-sonnet-4-6"


def test_executor_round_trips_through_markdown():
    s = load_slices(PLAN)
    md = slices_to_markdown(s)
    reparsed = {x.id: x for x in load_slices(md)}
    assert reparsed["T2"].executor == "opencode:opencode/claude-sonnet-4-6"
    # a slice with no executor must NOT emit a stray 'executor:' line
    assert reparsed["T1"].executor is None
