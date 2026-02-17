#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Iterable, Set

sys.path.append(os.path.dirname(__file__))

from generate_report import compute_hash, parse_frontmatter


def iter_report_files(daily_root: pathlib.Path) -> Iterable[pathlib.Path]:
    if not daily_root.exists():
        return []
    return daily_root.rglob("*.md")


def load_report_hash_index(daily_root: pathlib.Path) -> Set[str]:
    index_path = daily_root / ".report_hashes.json"
    if not index_path.exists():
        return set()
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if isinstance(data, list):
        return {str(item) for item in data if item}
    if isinstance(data, dict):
        return {str(k) for k in data.keys()}
    return set()


def collect_report_hashes(daily_root: pathlib.Path) -> Set[str]:
    hashes = load_report_hash_index(daily_root)
    if hashes:
        return hashes
    hashes = set()
    for path in iter_report_files(daily_root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = parse_frontmatter(text)
        input_hash = meta.get("input_hash")
        if input_hash:
            hashes.add(input_hash)
    return hashes


def iter_scratch_files(scratch_root: pathlib.Path) -> Iterable[pathlib.Path]:
    if not scratch_root.exists():
        return []
    for path in scratch_root.rglob("*"):
        if path.is_file():
            yield path


def cleanup_scratch(
    scratch_root: pathlib.Path,
    report_hashes: Set[str],
    dry_run: bool = False,
) -> list[pathlib.Path]:
    deleted: list[pathlib.Path] = []
    for path in iter_scratch_files(scratch_root):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        scratch_hash = compute_hash(content)
        if scratch_hash in report_hashes:
            deleted.append(path)
            if not dry_run:
                path.unlink()
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove scratch notes that already have generated reports."
    )
    parser.add_argument(
        "--scratch-root", default="scratch", help="Scratch notes directory"
    )
    parser.add_argument(
        "--daily-root", default="content/daily", help="Daily reports directory"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show deletions without removing"
    )
    args = parser.parse_args()

    scratch_root = pathlib.Path(args.scratch_root)
    daily_root = pathlib.Path(args.daily_root)

    report_hashes = collect_report_hashes(daily_root)
    if not report_hashes:
        print("No report hashes found. Nothing to delete.")
        return 0

    deleted = cleanup_scratch(scratch_root, report_hashes, dry_run=args.dry_run)
    if not deleted:
        print("No scratch notes matched generated reports.")
        return 0

    for path in deleted:
        print(f"Deleted: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
