"""v0.5.3 NOCREDS: CLD's code makes no explicit lookup of a credential-named variable.

Telemetry export goes to a configured endpoint only (a local OpenTelemetry Collector can hold
backend keys), and the optional behavioral judge takes its API key as an explicit argument.

The scan is a regression guard for explicit lookups, not a proof. Two disclosed reads are
dynamic and out of its reach: validation identity hashes the values of provider variables
selected by name pattern (admission.selected_environment; hashed locally, never stored or
sent), and Claude gateway mode checks that a gateway token is present."""
import inspect
import re
from pathlib import Path

from tests.evidence._lazy import resolve

ROOT = Path(__file__).resolve().parents[2]
_NAME = r"[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|HEADERS|CREDENTIALS?|AUTH)[A-Z0-9_]*"
CREDENTIAL_READ = re.compile(
    r"""(?:environ|env)\s*(?:\.\s*(?:get|pop|setdefault)\s*\(|\[)\s*["']""" + _NAME + r"""["']"""
    r"""|getenv\s*\(\s*["']""" + _NAME + r"""["']""")


def _target(env):
    return resolve("cld.cli", "_otel_target_from_env")(env)


def test_langfuse_keys_alone_no_longer_configure_export():
    assert _target({"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk",
                    "LANGFUSE_HOST": "https://h.example"}) is None


def test_endpoint_is_returned_without_reading_headers():
    target = _target({"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318/v1/traces",
                      "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Basic c2VjcmV0"})
    assert target == "http://localhost:4318/v1/traces", target


def test_status_line_points_at_the_endpoint_setting_only(monkeypatch):
    for name in ("OTEL_EXPORTER_OTLP_ENDPOINT", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    line = resolve("cld.cli", "_otel_status_line")()
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in line and "LANGFUSE" not in line, line


def test_compliance_judge_key_is_an_explicit_argument():
    params = inspect.signature(resolve("cld.behavioral", "make_compliance_metric")).parameters
    assert "api_key" in params and params["api_key"].default is None, list(params)


def test_scan_catches_the_lookup_forms_it_claims_to():
    for source in ('os.environ.get ("OPENAI_API_KEY")', "os.environ['AWS_ACCESS_KEY_ID']",
                   'env.pop("ANTHROPIC_AUTH_TOKEN", None)', 'os.getenv( "DB_PASSWORD")',
                   'environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "")'):
        assert CREDENTIAL_READ.search(source), source
    assert not CREDENTIAL_READ.search('os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")')


def test_engine_and_bundled_scripts_make_no_explicit_credential_lookup():
    roots = [ROOT / "engine", *sorted((ROOT / "plugins").glob("*/skills/*/scripts"))]
    hits = [f"{path.relative_to(ROOT).as_posix()}: {match.group(0)}"
            for root in roots for path in sorted(root.rglob("*.py"))
            for match in CREDENTIAL_READ.finditer(path.read_text(encoding="utf-8"))]
    assert not hits, hits
