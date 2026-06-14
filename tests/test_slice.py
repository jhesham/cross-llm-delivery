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


SUB_PLAN = """## SLICE: P1
brief: parent
files: src/p.py
acceptance_test_path: tests/test_p.py
deps:

## SUBSLICE: P1a
brief: child a
files: src/a.py
acceptance_test_path: tests/test_p.py::test_a
executor: cursor:composer-2.5

## SUBSLICE: P1b
brief: child b
files: src/b.py
acceptance_test_path: tests/test_p.py::test_b

## SLICE: P2
brief: standalone
files: src/q.py
acceptance_test_path: tests/test_q.py
deps: P1
"""


def test_subslices_parsed_under_parent():
    s = {x.id: x for x in load_slices(SUB_PLAN)}
    assert set(s) == {"P1", "P2"}            # subslices are NOT top-level slices
    assert [c.id for c in s["P1"].subslices] == ["P1a", "P1b"]
    assert s["P1"].subslices[0].parent_id == "P1"
    assert s["P1"].subslices[0].executor == "cursor:composer-2.5"
    assert s["P1"].subslices[1].executor is None
    assert s["P2"].subslices == []


def test_subslices_round_trip():
    md = slices_to_markdown(load_slices(SUB_PLAN))
    s = {x.id: x for x in load_slices(md)}
    assert [c.id for c in s["P1"].subslices] == ["P1a", "P1b"]
    # child fields survive the round-trip
    assert s["P1"].subslices[0].executor == "cursor:composer-2.5"
    assert s["P1"].subslices[0].parent_id == "P1"
    assert s["P1"].subslices[1].executor is None
