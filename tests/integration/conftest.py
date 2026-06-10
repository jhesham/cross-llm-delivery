"""Fixtures for real-git integration tests (B1.1 harness)."""

import pytest

from tests.integration.harness import init_repo


@pytest.fixture
def git_repo(tmp_path):
    """A real, initialized git repo (one commit, HEAD exists). Auto-cleaned by tmp_path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    return init_repo(repo)
