"""Atomic ledger replacement survives transient Windows reader locks."""
from pathlib import Path
import time

import pytest

from cld import recovery


def locked(code):
    error = PermissionError('simulated Windows replacement lock')
    error.winerror = code
    return error


@pytest.mark.parametrize('code', [5, 32, 33])
def test_transient_windows_lock_keeps_atomic_old_bytes_until_replace(tmp_path, monkeypatch, code):
    target = tmp_path / 'ledger.json'
    target.write_bytes(b'old')
    original = recovery.os.replace
    sources, sleeps = [], []

    def replace(source, destination):
        sources.append(Path(source))
        assert Path(source).read_bytes() == b'new'
        assert target.read_bytes() == b'old'
        if len(sources) < 3:
            raise locked(code)
        return original(source, destination)

    monkeypatch.setattr(recovery.os, 'replace', replace)
    monkeypatch.setattr(time, 'sleep', sleeps.append)
    recovery.atomic_write(target, b'new')
    assert target.read_bytes() == b'new'
    assert len(sources) == 3 and len(set(sources)) == 1
    assert len(sleeps) == 2 and all(0 < delay <= .1 for delay in sleeps)
    assert list(tmp_path.iterdir()) == [target]


def test_persistent_windows_lock_is_bounded_and_preserves_original(tmp_path, monkeypatch):
    target = tmp_path / 'ledger.json'
    target.write_bytes(b'old')
    calls, sleeps = [], []

    def replace(source, destination):
        calls.append(Path(source))
        raise locked(5)

    monkeypatch.setattr(recovery.os, 'replace', replace)
    monkeypatch.setattr(time, 'sleep', sleeps.append)
    with pytest.raises(PermissionError):
        recovery.atomic_write(target, b'new')
    assert 1 < len(calls) <= 10 and len(set(calls)) == 1
    assert len(sleeps) == len(calls) - 1 and sum(sleeps) <= 1
    assert target.read_bytes() == b'old'
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize('error', [PermissionError('POSIX denied'), locked(87), OSError('disk failure')])
def test_other_errors_fail_immediately_without_retry(tmp_path, monkeypatch, error):
    target = tmp_path / 'ledger.json'
    target.write_bytes(b'old')
    calls, sleeps = [], []

    def replace(source, destination):
        calls.append(source)
        raise error

    monkeypatch.setattr(recovery.os, 'replace', replace)
    monkeypatch.setattr(time, 'sleep', sleeps.append)
    with pytest.raises(type(error)):
        recovery.atomic_write(target, b'new')
    assert len(calls) == 1 and sleeps == []
    assert target.read_bytes() == b'old'
    assert list(tmp_path.iterdir()) == [target]
