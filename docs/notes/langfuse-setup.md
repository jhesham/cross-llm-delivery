# Langfuse setup — tracing target decision

**Date:** 2026-06-08 (T1.2)

## Decision: Langfuse Cloud (free tier)

**Why:** Docker is **not installed** on this machine (`docker --version` → command not found),
so the self-hosted `docker-compose` path from the plan is unavailable. Per the T1.2 Step-1
fork, we fall back to **Langfuse Cloud free tier**.

This is a real fork that was surfaced to the user. Self-hosting remains the preferred target
for a future public release (no external dependency, data stays local); revisit if/when Docker
is available, or document Docker as a prereq in the T6.2 sharing README.

## SDK version

Installed: **langfuse 4.7.1** (the editable install resolved `langfuse>=2.0` to v4, not v2).
The v4 client constructor accepts `public_key`, `secret_key`, and `host` keyword args
(confirmed via `inspect.signature`), so the tracing helper is forward-compatible. The v4
SDK is OpenTelemetry-based; for now we only need client initialization (the DoD is config
wiring, not live spans).

## Configuration (3 env vars)

The tracing helper reads these from the environment:

| Var | Purpose | Cloud value |
|---|---|---|
| `LANGFUSE_HOST` | API base URL | `https://cloud.langfuse.com` (EU) or `https://us.cloud.langfuse.com` (US) |
| `LANGFUSE_PUBLIC_KEY` | project public key | from Langfuse Cloud project settings (`pk-lf-...`) |
| `LANGFUSE_SECRET_KEY` | project secret key | from Langfuse Cloud project settings (`sk-lf-...`) |

To use real tracing: create a free project at https://cloud.langfuse.com, copy the keys,
and set the three vars in the environment (or a `.env` not committed). Without keys the
helper raises on init — by design, so misconfiguration fails loud rather than silently
dropping traces.

## How tracing is consumed (design context)

Langfuse is the **behavioral verification signal** (design doc, Verification Stack): Claude
judges executor/agent behavior by reading traces. Deterministic plumbing is judged by pytest;
behavior is judged via deepeval evals + Langfuse traces.
