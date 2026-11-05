"""Read-only model discovery for the CLI and installed host-agent picker."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from cld.models import build_model_index, render_executor_level, spec_with_effort
from cld.providers_api import all_providers, load_providers


def discover_model_index():
    """Discover only bundled providers; never run inference or update evidence."""
    load_providers()
    providers = {p.name for p in all_providers()}
    opencode, cursor, codex, claude = [], [], [], []
    if "opencode" in providers:
        from cld_providers.opencode.provider import list_models, _default_runner
        opencode = list_models(_default_runner)
    if "cursor" in providers:
        from cld_providers.cursor.provider import list_cursor_models, _default_runner
        cursor = list_cursor_models(_default_runner)
    if "codex" in providers:
        from cld_providers.codex.catalog import list_codex_models
        codex = list_codex_models()
    if "claude" in providers:
        from cld_providers.claude.catalog import CLAUDE_MODELS
        claude = CLAUDE_MODELS
    return build_model_index(opencode_ids=opencode, cursor_models=cursor,
        codex_models=codex, claude_models=claude, evidence={})


def main(argv=None):
    parser = argparse.ArgumentParser(description="List advisory executor choices; no dispatch or validation")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    index = discover_model_index()
    if args.json:
        rows = []
        for model in index:
            row = asdict(model)
            row["default_spec"] = (spec_with_effort(model, model.default_effort)
                if model.executor != "codex" or model.default_effort else None)
            row["service_tiers"] = ["standard", "fast"] if model.executor == "codex" else []
            rows.append(row)
        print(json.dumps({"models": rows, "advisory": True, "dispatches": 0}, ensure_ascii=True))
    else:
        print("\n".join(render_executor_level(index)[0]))
        for model in index:
            print(f"  {model.spec} ({model.headless_status}, {model.cost_class}); effort default: {model.default_effort or 'explicit choice'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
