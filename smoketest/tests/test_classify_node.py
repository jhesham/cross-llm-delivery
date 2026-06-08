from agent.state import State
from agent.classify_node import classify_node  # does not exist yet


class FakeModel:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.reply


def test_classify_node_sets_label_from_model():
    model = FakeModel(reply="positive")
    state: State = {"text": "I love this", "label": ""}
    result = classify_node(state, model)
    assert result["label"] == "positive"
    assert result["text"] == "I love this"  # node must not mutate input text


def test_classify_node_passes_text_to_model():
    model = FakeModel(reply="negative")
    classify_node({"text": "bad", "label": ""}, model)
    assert any("bad" in p for p in model.calls)  # text reached the model via the boundary
