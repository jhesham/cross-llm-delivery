# Slice: classify_node

Create `src/agent/classify_node.py` defining:
`def classify_node(state: State, model: ModelClient) -> State`

- Import `State` and `ModelClient` from `agent.state`. Do NOT modify state.py.
- Build a prompt from `state["text"]`, call `model.complete(prompt)`, set the returned
  string as `label`. Return a new/updated State; do not mutate `text`.
- All model access MUST go through the injected `model` param (no hardcoded clients/imports).

Definition of Done: `pytest -v` passes all tests in tests/test_classify_node.py.
