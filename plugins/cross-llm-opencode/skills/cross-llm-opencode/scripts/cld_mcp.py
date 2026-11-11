#!/usr/bin/env python
"""Run the bundled MCP server or a durable job's internal entrypoint."""

import argparse
import json
import os
import sys
from pathlib import Path

# Bundle shim: cld and cld_providers are vendored beside this script.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Monorepo shim: support a fresh clone without a package installation.
_engine_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "engine")
if os.path.isdir(os.path.join(_engine_dir, "cld")):
    sys.path.insert(1, _engine_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run-job", metavar="JOB_DIR")
    mode.add_argument("--resolve-job", metavar="JOB_ID")
    parser.add_argument("--confirm", action="store_true",
                        help="Confirm manual resolution of an uncertain job (human only).")
    args = parser.parse_args(argv)
    if args.confirm and args.resolve_job is None:
        parser.error("--confirm requires --resolve-job")
    if args.run_job is not None:
        from cld.mcp_jobs import run_job

        return run_job(args.run_job)
    if args.resolve_job is not None:
        if not args.confirm:
            parser.error("--resolve-job requires --confirm")
        from cld.mcp_jobs import resolve_job

        result = resolve_job(args.resolve_job, confirm=args.confirm)
        print(json.dumps(result))
        return 0

    from cld.mcp_server import main as server_main

    return server_main(scripts_dir=Path(__file__).resolve().parent)


if __name__ == "__main__":
    raise SystemExit(main())
