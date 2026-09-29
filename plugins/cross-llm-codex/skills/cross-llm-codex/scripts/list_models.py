#!/usr/bin/env python
"""Read-only picker discovery from source or a standalone generated skill."""
import os
import sys

_scripts = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _scripts)
_engine = os.path.join(os.path.dirname(os.path.dirname(_scripts)), "engine")
if os.path.isdir(os.path.join(_engine, "cld")):
    sys.path.insert(1, _engine)

from cld.picker import main

if __name__ == "__main__":
    raise SystemExit(main())
