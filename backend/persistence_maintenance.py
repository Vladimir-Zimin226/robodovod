"""Narrow maintenance commands for project persistence."""

from __future__ import annotations

import argparse

from database import get_database
from persistence_api import purge_expired_tombstones


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("purge-deletion-tombstones",))
    args = parser.parse_args()
    if args.command == "purge-deletion-tombstones":
        with get_database().session() as db:
            count = purge_expired_tombstones(db)
        print(f"purged deletion tombstones: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
