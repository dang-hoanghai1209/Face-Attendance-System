import argparse
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.security_snapshot_cleanup_service import cleanup_security_snapshots


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean old security snapshot files.")
    parser.add_argument("--days", type=int, default=30, help="Delete snapshots older than this many days.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Scan only; do not delete files.")
    parser.add_argument("--delete", action="store_true", help="Actually delete files older than --days.")
    args = parser.parse_args()

    summary = cleanup_security_snapshots(days=args.days, dry_run=not args.delete)
    print(
        "scanned={scanned} deleted={deleted} skipped={skipped} dry_run={dry_run} root={root}".format(
            **summary
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
