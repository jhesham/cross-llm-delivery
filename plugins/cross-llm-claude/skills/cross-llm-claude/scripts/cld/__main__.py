"""Module entrypoint: ``python -m cld ...`` runs the engine-owned delivery CLI.

Equivalent to ``python skill/scripts/run_delivery.py ...``; the reusable command
handling lives in :mod:`cld.cli`.
"""

from cld.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
