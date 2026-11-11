"""v0.7.1: a lock file initialised by another process never surfaces as PermissionError.

On Windows, a second opener that saw an empty lock file writes its initial byte into
a region the first owner has already locked; that must count as contention.
"""
import os

import pytest

from cld.locking import OwnerBusy, file_owner


@pytest.mark.skipif(os.name != "nt", reason="Windows byte-range locks")
def test_initialising_write_into_a_locked_region_is_contention(tmp_path):
    import msvcrt
    path = tmp_path / "race.lock"
    path.write_bytes(b"")
    holder = open(path, "r+b")
    try:
        msvcrt.locking(holder.fileno(), msvcrt.LK_NBLCK, 1)  # owner locks byte 0 of an empty file
        try:
            with file_owner(path, wait_seconds=0):
                raise AssertionError("acquired a lock another owner holds")
        except OwnerBusy:
            pass
        except PermissionError as exc:
            raise AssertionError(f"contention surfaced as {exc!r}") from None
    finally:
        holder.seek(0)
        msvcrt.locking(holder.fileno(), msvcrt.LK_UNLCK, 1)
        holder.close()
