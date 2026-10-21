"""Check repository file citations in a knowledge-base module."""

import re
from urllib.parse import unquote, urlsplit


_URL_RE = re.compile(r"https://[^\s<>\"']+")
_TRAILING_PUNCTUATION = ",.;:!?)]}`"


def _repository_citations(text: str):
    """Yield (host, owner, repo, path) for GitHub-style blob URLs in text."""
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(_TRAILING_PUNCTUATION)
        parsed = urlsplit(url)
        parts = parsed.path.strip("/").split("/")
        if len(parts) < 5 or parts[2] != "blob":
            continue
        host = parsed.netloc
        owner, repo = unquote(parts[0]), unquote(parts[1])
        path = "/".join(unquote(part) for part in parts[4:])
        if host and owner and repo and path:
            yield host, owner, repo, path


def _return_code(result):
    """Accept subprocess-like results and the compact (rc, output) runner form."""
    if isinstance(result, tuple):
        return result[0] if result else 1
    return getattr(result, "returncode", result)


def verify_citations(text: str, freshness: dict[str, str], *, runner) -> list[str]:
    """Check blob links against the commit recorded for each ``owner/repo``.

    ``runner`` is called as ``runner(argv, cwd)`` and may return either a
    ``subprocess.CompletedProcess`` or ``(returncode, output)``.
    """
    problems = []
    for host, owner, repo, path in _repository_citations(text):
        key = f"{owner}/{repo}"
        sha = freshness.get(key)
        if not sha:
            problems.append(f"Missing freshness entry for {key}; cannot verify {path}")
            continue

        argv = [
            "gh",
            "api",
            "--hostname",
            host,
            f"repos/{owner}/{repo}/contents/{path}?ref={sha}",
        ]
        try:
            result = runner(argv, ".")
            rc = _return_code(result)
        except Exception as exc:
            problems.append(f"Could not verify citation path {path}: {exc}")
            continue
        if rc != 0:
            problems.append(f"Citation path {path} could not be verified (gh api exit code {rc})")
    return problems
