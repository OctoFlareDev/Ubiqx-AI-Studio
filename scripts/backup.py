#!/usr/bin/env python3
"""Back up or restore the local Ubiqx data directory.

Usage:
    python scripts/backup.py backup --out /path/to/backup.tar.gz
    python scripts/backup.py restore /path/to/backup.tar.gz

Restore should run while the API service is stopped.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from app.config import settings  # noqa: E402
from app.ops import backup, restore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ubiqx local backup and restore")
    sub = parser.add_subparsers(dest="command", required=True)

    backup_parser = sub.add_parser("backup", help="Write a backup archive")
    backup_parser.add_argument("--out", required=True, help="Path to the .tar.gz archive to write")

    restore_parser = sub.add_parser("restore", help="Restore from a backup archive")
    restore_parser.add_argument("archive", help="Path to the .tar.gz archive")

    args = parser.parse_args()
    if args.command == "backup":
        result = backup(settings.data_dir, Path(args.out))
        print(f"Backed up {result['file_count']} files to {result['archive']}")
    else:
        restore(Path(args.archive), settings.data_dir)
        print(f"Restored {args.archive} into {settings.data_dir}")


if __name__ == "__main__":
    main()
