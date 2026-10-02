"""Curated, local-only Claude model metadata for the advisory picker."""
from __future__ import annotations

from dataclasses import dataclass


EFFORTS = ("low", "medium", "high", "xhigh", "max")


@dataclass(frozen=True)
class ClaudeModel:
    id: str
    label: str
    efforts: tuple[str, ...]


CLAUDE_MODELS = (
    ClaudeModel("claude-sonnet-5", "Claude Sonnet 5", EFFORTS),
    ClaudeModel("claude-opus-5-5", "Claude Opus 5.5", EFFORTS),
    ClaudeModel("claude-fable-5-1", "Claude Fable 5.1", EFFORTS),
    ClaudeModel("claude-haiku-4-5", "Claude Haiku 4.5", EFFORTS),
)


def list_models(runner=None) -> list[str]:
    """Return curated IDs without querying a CLI or account."""
    return [model.id for model in CLAUDE_MODELS]
