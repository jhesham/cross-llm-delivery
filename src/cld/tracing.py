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
