"""Model-free Claude CLI authentication preflight helpers."""

from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import urlsplit


def claude_mode(environ) -> str:
    """Return the selected Claude authentication mode, defaulting to subscription."""
    value = environ.get("CLD_CLAUDE_MODE")
    if value is None or value == "":
        return "subscription"
    if value in ("subscription", "gateway"):
        return value
    raise ValueError("CLD_CLAUDE_MODE must be 'subscription' or 'gateway'.")


def _hostname(base_url) -> str | None:
    if not isinstance(base_url, str) or not base_url:
        return None
    try:
        return urlsplit(base_url).hostname
    except ValueError:
        # URL parser errors can include user-supplied URL data; keep them private.
        return None


def gateway_host(environ, settings_file: Path) -> str | None:
    """Return only the gateway hostname configured in the environment or settings."""
    base_url = environ.get("ANTHROPIC_BASE_URL")
    if base_url:
        return _hostname(base_url)

    try:
        payload = json.loads(Path(settings_file).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    settings_env = payload.get("env")
    if not isinstance(settings_env, dict):
        return None
    return _hostname(settings_env.get("ANTHROPIC_BASE_URL"))


@dataclass(frozen=True)
class AuthStatus:
    """Non-secret account details reported by ``claude auth status``."""

    logged_in: bool
    auth_method: str | None
    org_id: str | None
    subscription_type: str | None


def parse_auth_status(text: str) -> AuthStatus:
    """Parse the JSON object from ``claude auth status`` without retaining it."""
    if not isinstance(text, str):
        raise ValueError("Invalid Claude auth status JSON.")

    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        # Do not include parser diagnostics: they retain the input document.
        raise ValueError("Invalid Claude auth status JSON.") from None

    if not isinstance(payload, dict) or type(payload.get("loggedIn")) is not bool:
        raise ValueError("Invalid Claude auth status JSON.")

    fields = ("authMethod", "orgId", "subscriptionType")
    if any(payload.get(name) is not None and not isinstance(payload.get(name), str)
           for name in fields):
        raise ValueError("Invalid Claude auth status JSON.")

    return AuthStatus(
        logged_in=payload["loggedIn"],
        auth_method=payload.get("authMethod"),
        org_id=payload.get("orgId"),
        subscription_type=payload.get("subscriptionType"),
    )


def auth_problem(status: AuthStatus, *, mode="subscription", gateway=None) -> str | None:
    """Return a safe, actionable message unless the selected auth mode is ready."""
    mode = claude_mode({"CLD_CLAUDE_MODE": mode})
    if mode == "gateway":
        if not status.logged_in:
            return "Claude CLI is not logged in. Run `claude auth login` first."
        if not gateway:
            return "Gateway mode requires ANTHROPIC_BASE_URL to be configured."
        return None
    if gateway:
        return ("Claude CLI is routed through a gateway. Set CLD_CLAUDE_MODE=gateway "
                "to use gateway authentication.")
    if not status.logged_in:
        return "Claude CLI is not logged in. Run `claude auth login` first."
    if status.auth_method != "claude.ai":
        return ("Claude CLI requires subscription authentication (`claude.ai`); "
                f"the current auth method is {status.auth_method!r}.")
    return None


def account_context(status: AuthStatus, *, mode="subscription", gateway=None) -> str:
    """Return the stable account marker used to scope validation evidence."""
    mode = claude_mode({"CLD_CLAUDE_MODE": mode})
    if mode == "gateway":
        return f"claude-gateway:{gateway or 'unknown'}"
    org_id = status.org_id or "unknown"
    subscription_type = status.subscription_type or "unknown"
    return f"claude-account:{org_id}:{subscription_type}"


def run_auth_preflight(runner, command: str) -> tuple[AuthStatus | None, str | None]:
    """Run one injected ``claude auth status`` command and classify its result."""
    try:
        result = runner([command, "auth", "status"], ".")
    except Exception:
        # Runner exceptions can contain command output or environment details.
        return None, "Could not run `claude auth status`."

    if not isinstance(result, tuple) or len(result) != 2:
        return None, "Invalid result from `claude auth status`."

    returncode, stdout = result
    if returncode != 0:
        return None, "`claude auth status` exited unsuccessfully."

    try:
        status = parse_auth_status(stdout)
    except ValueError:
        return None, "`claude auth status` returned invalid status JSON."

    return status, auth_problem(status)
