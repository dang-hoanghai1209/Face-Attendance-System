from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
SECURITY_SNAPSHOTS_DIR = BASE_DIR / "media" / "security_snapshots"


@dataclass(frozen=True)
class SnapshotCleanupSummary:
    scanned: int = 0
    deleted: int = 0
    skipped: int = 0
    dry_run: bool = True
    root: str = ""

    def as_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "deleted": self.deleted,
            "skipped": self.skipped,
            "dry_run": self.dry_run,
            "root": self.root,
        }


def cleanup_security_snapshots(days: int, *, dry_run: bool = True, root_path: Path | str | None = None) -> dict:
    if days < 1:
        raise ValueError("days must be >= 1")

    root = _resolve_cleanup_root(root_path)
    if not root.exists():
        return SnapshotCleanupSummary(dry_run=dry_run, root=str(root)).as_dict()

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    scanned = 0
    deleted = 0
    skipped = 0

    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        scanned += 1
        try:
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            skipped += 1
            continue

        if modified_at >= cutoff:
            skipped += 1
            continue

        if dry_run:
            skipped += 1
            continue

        try:
            path.unlink()
            deleted += 1
        except OSError:
            skipped += 1

    _remove_empty_dirs(root, dry_run=dry_run)
    return SnapshotCleanupSummary(scanned=scanned, deleted=deleted, skipped=skipped, dry_run=dry_run, root=str(root)).as_dict()


def _resolve_cleanup_root(root_path: Path | str | None) -> Path:
    configured_root = SECURITY_SNAPSHOTS_DIR.resolve()
    root = Path(root_path).resolve() if root_path is not None else configured_root

    if root != configured_root:
        raise ValueError(f"cleanup root must be {configured_root}")
    return root


def _remove_empty_dirs(root: Path, *, dry_run: bool) -> None:
    if dry_run or not root.exists():
        return
    for directory in sorted((path for path in root.rglob("*") if path.is_dir()), key=lambda path: len(path.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            continue
