"""T16 offline acceptance baseline; provider registration follows lead review."""


class CodexExecutor:
    def __init__(self, *, model, effort=None, sandbox="workspace-write", runner=None,
                 git_runner=None, timeout=None, cancel=None, artifact_dir=None):
        self.model = model

    def run(self, task, workdir, feedback=None):
        assert False, "T16 adapter acceptance baseline"
