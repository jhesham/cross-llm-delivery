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


def test_subslice_marker_is_not_special_anymore():
    # "## SUBSLICE:" lines must no longer create children; only top-level slices parse.
    from cld.plan.slice import load_slices
    md = ("## SLICE: P1\nbrief: p\nfiles: a.py\nacceptance_test_path: t.py\ndeps:\n\n"
          "## SUBSLICE: P1a\nbrief: c\nfiles: b.py\nacceptance_test_path: t.py\n")
    slices = load_slices(md)
    assert [s.id for s in slices] == ["P1"]          # P1a is NOT parsed as anything
    assert not hasattr(slices[0], "subslices")        # field removed


def test_complexity_parsed_and_defaulted():
    from cld.plan.slice import load_slices
    md = ("## SLICE: A\nbrief: a\nfiles: a.py\nacceptance_test_path: t.py\ncomplexity: easy\ndeps:\n\n"
          "## SLICE: B\nbrief: b\nfiles: b.py\nacceptance_test_path: t.py\ndeps: A\n")
    s = {x.id: x for x in load_slices(md)}
    assert s["A"].complexity == "easy"
    assert s["B"].complexity == "standard"   # omitted -> default


def test_complexity_round_trips():
    from cld.plan.slice import load_slices, slices_to_markdown
    md = "## SLICE: A\nbrief: a\nfiles: a.py\nacceptance_test_path: t.py\ncomplexity: complex\ndeps:\n"
    s = {x.id: x for x in load_slices(slices_to_markdown(load_slices(md)))}
    assert s["A"].complexity == "complex"
