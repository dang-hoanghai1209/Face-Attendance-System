import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services import security_snapshot_cleanup_service as cleanup_service


def write_snapshot(path: Path, *, age_days: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"snapshot")
    timestamp = (datetime.now(timezone.utc) - timedelta(days=age_days)).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path


def test_cleanup_dry_run_does_not_delete_old_files(tmp_path, monkeypatch):
    root = tmp_path / "security_snapshots"
    old_file = write_snapshot(root / "1" / "old.jpg", age_days=40)
    monkeypatch.setattr(cleanup_service, "SECURITY_SNAPSHOTS_DIR", root)

    summary = cleanup_service.cleanup_security_snapshots(days=30, dry_run=True)

    assert summary["scanned"] == 1
    assert summary["deleted"] == 0
    assert summary["skipped"] == 1
    assert old_file.exists()


def test_cleanup_delete_removes_only_old_files(tmp_path, monkeypatch):
    root = tmp_path / "security_snapshots"
    old_file = write_snapshot(root / "1" / "old.jpg", age_days=40)
    new_file = write_snapshot(root / "1" / "new.jpg", age_days=2)
    monkeypatch.setattr(cleanup_service, "SECURITY_SNAPSHOTS_DIR", root)

    summary = cleanup_service.cleanup_security_snapshots(days=30, dry_run=False)

    assert summary["scanned"] == 2
    assert summary["deleted"] == 1
    assert not old_file.exists()
    assert new_file.exists()


def test_cleanup_rejects_unsafe_root_path(tmp_path, monkeypatch):
    safe_root = tmp_path / "security_snapshots"
    unsafe_root = tmp_path / "other"
    monkeypatch.setattr(cleanup_service, "SECURITY_SNAPSHOTS_DIR", safe_root)

    with pytest.raises(ValueError, match="cleanup root must be"):
        cleanup_service.cleanup_security_snapshots(days=30, dry_run=True, root_path=unsafe_root)
