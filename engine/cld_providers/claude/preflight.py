"""Model-free Claude CLI authentication preflight helpers."""

from dataclasses import dataclass
import json


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


def auth_problem(status: AuthStatus) -> str | None:
    """Return a safe, actionable message unless subscription login is active."""
    if not status.logged_in:
        return "Claude CLI is not logged in. Run `claude auth login` first."
    if status.auth_method != "claude.ai":
        return ("Claude CLI requires subscription authentication (`claude.ai`); "
                f"the current auth method is {status.auth_method!r}.")
    return None


def account_context(status: AuthStatus) -> str:
    """Return the stable account marker used to scope validation evidence."""
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
