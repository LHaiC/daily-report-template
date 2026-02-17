import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import hashlib

# Import the module to test
# We need to add scripts to sys.path to import it
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
import generate_report


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("REPORT_API_KEY", "fake-key")
    monkeypatch.setenv("REPORT_API_URL", "http://fake-api")


@pytest.fixture
def temp_files(tmp_path):
    input_file = tmp_path / "notes.md"
    output_file = tmp_path / "report.md"
    input_file.write_text("Original content")
    return input_file, output_file


def compute_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_hashing_and_generation(mock_env, temp_files):
    input_file, output_file = temp_files

    # Mock the API call to return a valid report
    with patch("generate_report.call_cloud_api") as mock_api:
        mock_api.return_value = "---\ntitle: Test\ntags: [test]\n---\n# Report\n..."

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--input",
                str(input_file),
                "--output",
                str(output_file),
                "--date",
                "2023-01-01",
            ],
        ):
            exit_code = generate_report.main()

        assert exit_code == 0

        # The script renames the file based on the title "Test" -> "test"
        # Original output_file is "report.md", so parent dir is tmp_path
        expected_new_file = output_file.parent / "2023-01-01-test.md"

        assert expected_new_file.exists()
        content = expected_new_file.read_text()
        assert "input_hash:" in content
        assert compute_hash("Original content") in content
        # Hash index should be updated
        index_path = expected_new_file.parent / ".report_hashes.json"
        assert index_path.exists()


def test_idempotency_skip(mock_env, temp_files):
    input_file, output_file = temp_files
    input_hash = compute_hash("Original content")

    # Create an existing report with the SAME hash
    output_file.write_text(
        f"---\ntitle: Old\ninput_hash: {input_hash}\n---\nOld content"
    )

    with patch("generate_report.call_cloud_api") as mock_api:
        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--input",
                str(input_file),
                "--output",
                str(output_file),
                "--date",
                "2023-01-01",
            ],
        ):
            exit_code = generate_report.main()

        # Should exit 0 and NOT call API
        assert exit_code == 0
        mock_api.assert_not_called()


def test_force_regeneration(mock_env, temp_files):
    input_file, output_file = temp_files
    input_hash = compute_hash("Original content")

    # Create an existing report with the SAME hash at the EXPECTED location
    # Note: If the previous run generated a slugified name, this check would fail if we passed the wrong path.
    # Here we assume the user/workflow passes the 'standard' path and the script checks it.
    output_file.write_text(
        f"---\ntitle: Old\ninput_hash: {input_hash}\n---\nOld content"
    )
    # Seed hash index to trigger fast-path skip
    index_path = output_file.parent / ".report_hashes.json"
    index_path.write_text(f'["{input_hash}"]', encoding="utf-8")

    with patch("generate_report.call_cloud_api") as mock_api:
        # The new generation has a different title "New", so it will produce a NEW filename
        mock_api.return_value = "---\ntitle: New\ntags: [new]\n---\nNew content"

        # Run with --force
        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--input",
                str(input_file),
                "--output",
                str(output_file),
                "--date",
                "2023-01-01",
                "--force",
            ],
        ):
            exit_code = generate_report.main()

        # Should call API despite matching hash
        assert exit_code == 0
        mock_api.assert_called_once()

        # Check the NEW file
        expected_new_file = output_file.parent / "2023-01-01-new.md"
        assert expected_new_file.exists()
        assert "New content" in expected_new_file.read_text()


def test_standardization_failure(mock_env, temp_files):
    input_file, output_file = temp_files

    # Mock API returning bad content (no tags, no title in frontmatter)
    with patch("generate_report.call_cloud_api") as mock_api:
        # The script will try to extract title from "# Just a header" -> "Just a header"
        # And slugify it -> "just-a-header"
        mock_api.return_value = "# Just a header\nNo frontmatter here."

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--input",
                str(input_file),
                "--output",
                str(output_file),
                "--date",
                "2023-01-01",
            ],
        ):
            exit_code = generate_report.main()

        # Should return 2 (Needs Review)
        assert exit_code == 2

        # Check for the renamed file
        expected_new_file = output_file.parent / "2023-01-01-just-a-header.md"
        assert expected_new_file.exists()

        content = expected_new_file.read_text()
        assert "tags: [untagged]" in content or "input_hash" in content
