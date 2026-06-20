"""Langfuse tracing helper.

Langfuse is the behavioral-verification signal (see design doc): Claude judges
executor/agent behavior by reading traces. This module only handles client
initialization from the environment; span emission is added where nodes run.

Target = Langfuse Cloud (Docker absent on this machine; see
docs/notes/langfuse-setup.md). SDK = langfuse v4 (OpenTelemetry-based); the
constructor accepts host/public_key/secret_key kwargs.

Missing keys raise on init by design — misconfiguration should fail loud rather
than silently drop traces.
"""

import os
from functools import lru_cache

from langfuse import Langfuse

# Default to Langfuse Cloud (EU). Override with LANGFUSE_HOST (e.g. the US host
# or a future self-hosted instance).
DEFAULT_HOST = "https://cloud.langfuse.com"


@lru_cache
def get_tracer() -> Langfuse:
    """Return a cached Langfuse client built from the environment.

    Reads LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY (required) and
    LANGFUSE_HOST (optional, defaults to Langfuse Cloud). Raises KeyError if a
    required key is missing — intentional fail-loud behavior.
    """
    return Langfuse(
        host=os.environ.get("LANGFUSE_HOST", DEFAULT_HOST),
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    )


def record_dispatch(
    *,
    slice_id: str,
    model: str,
    token_usage: dict,
    accepted: bool,
    attempts: int,
    diff_len: int,
    failing_tests: list,
    tracer=None,
) -> None:
    """Emit one observability span per executor dispatch.

    This is the integration point that makes a real run observable: each Gemini
    dispatch records what slice ran, on which model, the token usage, whether the
    judge accepted it, retry count, diff size, and any failing tests.

    Safety contract (load-bearing): this is **best-effort and never raises**.
    - If no `tracer` is passed, it tries `get_tracer()`; when Langfuse keys are
      absent that raises, which we swallow → tracing is simply OFF (the current
      default state). Missing observability must never break the build pipeline.
    - Any error from the tracer itself is also swallowed.

    `tracer` is injectable so tests (and alternative backends) can capture spans
    without a live Langfuse. The tracer is expected to expose
    `span(*, name, metadata)`.
    """
    if tracer is None:
        try:
            tracer = get_tracer()
        except Exception:
            return  # no keys / no client → tracing off, no-op

    metadata = {
        "slice_id": slice_id,
        "model": model,
        "token_usage": token_usage,
        "accepted": accepted,
        "attempts": attempts,
        "diff_len": diff_len,
        "failing_tests": failing_tests,
    }
    try:
        tracer.span(name=f"dispatch:{slice_id}", metadata=metadata)
    except Exception:
        return  # observability is best-effort; never break the pipeline
