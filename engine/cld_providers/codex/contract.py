"""Offline Codex exec boundary. T15 acceptance defines the implementation."""


class CodexContractError(ValueError):
    """Unsupported or unsafe Codex executor configuration/output."""


def check_capabilities(version_output, help_output):
    assert False, "T15 acceptance baseline"


def build_invocation(model, cwd, prompt, *, effort=None, sandbox="workspace-write", depth=0):
    assert False, "T15 acceptance baseline"


def parse_exec_output(stdout, stderr, returncode, *, process_error=None):
    assert False, "T15 acceptance baseline"
