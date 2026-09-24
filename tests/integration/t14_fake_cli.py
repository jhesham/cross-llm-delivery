"""Subprocess entrypoint for the T14 offline, fresh-session acceptance rehearsal."""

import sys

from cld import cli
from tests.integration.harness import FileCreatingExecutor


CONTENTS = {
    "a.py": "VALUE = 2\n",
    "b.py": "from a import VALUE\nRESULT = VALUE + 3\n",
}


def prepare_dispatch(_args, _slices, _ledger):
    return (lambda _spec: FileCreatingExecutor(contents=CONTENTS), None)


cli.prepare_dispatch = prepare_dispatch

if __name__ == "__main__":
    sys.exit(cli.main(sys.argv[1:]))
