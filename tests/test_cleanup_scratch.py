import os
import pathlib
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))

from cleanup_scratch import collect_report_hashes, cleanup_scratch
from generate_report import compute_hash


def test_cleanup_scratch_removes_matched(tmp_path: pathlib.Path) -> None:
    scratch_root = tmp_path / "scratch"
    daily_root = tmp_path / "content" / "daily"
    scratch_root.mkdir(parents=True)
    daily_root.mkdir(parents=True)

    scratch_note = scratch_root / "note.md"
    scratch_note.write_text("hello world", encoding="utf-8")

    unmatched_note = scratch_root / "keep.md"
    unmatched_note.write_text("keep me", encoding="utf-8")

    report_hash = compute_hash("hello world")
    report_path = daily_root / "2026-02-17-test.md"
    report_path.write_text(
        "---\ninput_hash: {}\n---\nbody\n".format(report_hash), encoding="utf-8"
    )

    hashes = collect_report_hashes(daily_root)
    deleted = cleanup_scratch(scratch_root, hashes)

    assert scratch_note in deleted
    assert not scratch_note.exists()
    assert unmatched_note.exists()


def test_cleanup_scratch_dry_run(tmp_path: pathlib.Path) -> None:
    scratch_root = tmp_path / "scratch"
    daily_root = tmp_path / "content" / "daily"
    scratch_root.mkdir(parents=True)
    daily_root.mkdir(parents=True)

    scratch_note = scratch_root / "note.md"
    scratch_note.write_text("hello world", encoding="utf-8")

    report_hash = compute_hash("hello world")
    report_path = daily_root / "2026-02-17-test.md"
    report_path.write_text(
        "---\ninput_hash: {}\n---\nbody\n".format(report_hash), encoding="utf-8"
    )

    hashes = collect_report_hashes(daily_root)
    deleted = cleanup_scratch(scratch_root, hashes, dry_run=True)

    assert scratch_note in deleted
    assert scratch_note.exists()
