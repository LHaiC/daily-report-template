import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add scripts to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
import generate_report


@pytest.fixture
def temp_env(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_API_KEY", "fake")
    monkeypatch.setenv("REPORT_API_URL", "http://fake")
    d = tmp_path / "daily"
    d.mkdir()
    return d


def test_slug_renaming(temp_env, capsys):
    input_file = temp_env / "input.md"
    input_file.write_text("Notes")

    # Initial expected output path
    initial_output = temp_env / "2023-01-01-initial.md"

    # Mock API to return a specific slug
    with patch("generate_report.call_cloud_api") as mock_api:
        mock_api.return_value = """---
title: "My Great Day"
slug: "my-great-day"
tags: ["test"]
---
# Content
"""

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--input",
                str(input_file),
                "--output",
                str(initial_output),
                "--date",
                "2023-01-01",
            ],
        ):
            exit_code = generate_report.main()

    assert exit_code == 0

    # The initial file should NOT exist (or at least, the final file should be the new one)
    # The script writes to the new path
    expected_new_path = temp_env / "2023-01-01-my-great-day.md"
    assert expected_new_path.exists()

    # Check stdout for REPORT_PATH
    captured = capsys.readouterr()
    assert f"REPORT_PATH={expected_new_path}" in captured.out


def test_slug_fallback(temp_env, capsys):
    input_file = temp_env / "input.md"
    input_file.write_text("Notes")
    initial_output = temp_env / "2023-01-01-initial.md"

    # Mock API with NO slug
    with patch("generate_report.call_cloud_api") as mock_api:
        mock_api.return_value = """---
title: "Just Title"
tags: ["test"]
---
# Content
"""
        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--input",
                str(input_file),
                "--output",
                str(initial_output),
                "--date",
                "2023-01-01",
            ],
        ):
            generate_report.main()

    # Should fallback to initial path OR slugified title
    # In my code: "If LLM didn't provide slug, try to make one from title"
    # So "Just Title" -> "just-title"
    expected_path = temp_env / "2023-01-01-just-title.md"
    assert expected_path.exists()


def test_default_output_if_no_slug_no_title(temp_env):
    input_file = temp_env / "input.md"
    input_file.write_text("Notes")
    initial_output = temp_env / "2023-01-01-initial.md"

    # Mock API with essentially empty frontmatter but a header
    with patch("generate_report.call_cloud_api") as mock_api:
        mock_api.return_value = "# Just content"

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--input",
                str(input_file),
                "--output",
                str(initial_output),
                "--date",
                "2023-01-01",
            ],
        ):
            generate_report.main()

    # The script sees "# Just content", extracts "Just content" as title.
    # It slugifies it to "just-content".
    # It constructs "2023-01-01-just-content.md".

    expected_path = temp_env / "2023-01-01-just-content.md"
    assert expected_path.exists()
