"""Turn an unexpected exception into an assertion, so a missing feature fails red by AssertionError only."""


def must(fn, *args, **kwargs):
    error = None
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # the assertion is raised outside the handler
        error = f"{type(exc).__name__}: {exc}"
    assert error is None, error
