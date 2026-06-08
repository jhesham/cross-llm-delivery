from typing import TypedDict, Protocol


class ModelClient(Protocol):
    """Injectable model boundary — nodes must call models only through this."""
    def complete(self, prompt: str) -> str: ...


class State(TypedDict):
    text: str
    label: str
