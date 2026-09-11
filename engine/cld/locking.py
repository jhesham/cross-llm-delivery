"""Local OS ownership. Readers need no lock; process exit releases writers."""
from contextlib import contextmanager
from pathlib import Path
import os
import time


class OwnerBusy(RuntimeError):
    pass


@contextmanager
def file_owner(path, *, wait_seconds=0):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() != path.absolute():
        raise RuntimeError(f"Lock path is redirected: {path}")
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise OwnerBusy(f"Active writer owns {path}; retry after it exits") from exc
                time.sleep(0.02)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
