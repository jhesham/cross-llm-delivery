"""Publish targets loader - maps providers to their git remote URLs."""

from pathlib import Path
import tomllib


def load_publish_targets(path) -> dict:
    """
    Load publish targets from a TOML file.

    Args:
        path: Path to the publish-targets.toml file.

    Returns:
        dict: Maps provider names to remote URLs, including "all" for umbrella.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is malformed TOML.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Publish targets file not found: {path}")

    with open(path, "rb") as f:
        targets = tomllib.load(f)

    return targets
