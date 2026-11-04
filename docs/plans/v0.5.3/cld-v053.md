## SLICE: NOCREDS
brief: CLD's own code must read no credential from the environment. In engine/cld/cli.py change _otel_target_from_env(env=None) to return only the endpoint string from OTEL_EXPORTER_OTLP_ENDPOINT (stripped; None when unset or blank): remove the LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY/LANGFUSE_HOST convenience, the Basic-auth header and the OTEL_EXPORTER_OTLP_HEADERS parsing, and drop the now unused base64 import. Update _maybe_otel_sink to build OTLPSpanExporter(endpoint=endpoint) with no headers argument, and _otel_status_line to use the string target; its OFF message must read "otel: OFF (set OTEL_EXPORTER_OTLP_ENDPOINT, for example a local OpenTelemetry Collector; see references/observability.md)" and the other two messages keep their meaning. Update docstrings to say CLD sends no credentials and that a collector can hold backend keys. In engine/cld/behavioral.py make_compliance_metric gains a keyword api_key: str | None = None and stops reading ANTHROPIC_API_KEY from the environment: pass api_key when given, else the existing "offline-placeholder"; update its docstring to say the caller passes the judge's key explicitly. No other behaviour changes.
files: engine/cld/cli.py, engine/cld/behavioral.py
acceptance_test_path: tests/v053/test_no_credentials.py
deps:
complexity: easy

## SLICE: LISTING
brief: In generator/build_plugins.py add plugin-directory listing fields to the Claude Code host manifest only (_main_claude), not to the Codex manifest: "displayName": f"Cross-LLM {PROVIDER_LABELS[p]}", "documentationUrl": f"{PROJECT_URL}#readme", "privacyPolicyUrl": f"{PROJECT_URL}/blob/main/PRIVACY.md", and "keywords": a list of at most 8 unique lowercase hyphenated words that includes the provider id p and "acceptance-tests" (use ["cross-llm", "delegation", "acceptance-tests", "git-worktrees", "test-gated", p]). Define the shared values as a module constant next to LISTING and keep LISTING itself unchanged because the Codex manifest also uses it. Do not add termsOfServiceUrl. Update the module docstring's metadata sentence to mention the new fields.
files: generator/build_plugins.py
acceptance_test_path: tests/v053/test_listing_metadata.py
deps:
complexity: easy
