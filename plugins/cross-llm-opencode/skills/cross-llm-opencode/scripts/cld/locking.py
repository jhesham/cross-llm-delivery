"""Local OS ownership. Readers need no lock; process exit releases writers."""
from contextlib import contextmanager
from pathlib import Path
import os
import time


class OwnerBusy(RuntimeError):
    pass


@contextmanager
def file_owner(path, *, wait_seconds=0, cancel=None):
    """Own *path* exclusively. A set *cancel* event ends the wait, and is checked
    again once the lock is held, by raising KeyboardInterrupt."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() != path.absolute():
        raise RuntimeError(f"Lock path is redirected: {path}")
    # Unbuffered: a refused initialising write must not linger and resurface on seek.
    with path.open("a+b", buffering=0) as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            try:
                stream.write(b"0")
                stream.flush()
            except OSError:
                # Another opener initialised and locked the byte first (Windows
                # byte-range lock); that is contention, decided by the lock below.
                pass
        stream.seek(0)
        deadline = time.monotonic() + wait_seconds
        while True:
            if cancel is not None and cancel.is_set():
                raise KeyboardInterrupt(f"Cancelled while waiting for {path}")
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
            if cancel is not None and cancel.is_set():
                raise KeyboardInterrupt(f"Cancelled after acquiring {path}")
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
