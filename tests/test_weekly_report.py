import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import datetime as dt

# Add scripts to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
import generate_weekly_report


@pytest.fixture
def mock_dailies(tmp_path):
    d1 = tmp_path / "2023-01-01-note.md"
    d1.write_text("# Day 1\n## Metrics\n- Metric A: 10\n- Metric B: 5\n## Other\n...")

    d2 = tmp_path / "2023-01-02-note.md"
    d2.write_text("# Day 2\n## Metrics\n- Metric A: 12\n")

    return [d1, d2]


def test_extract_metrics(mock_dailies):
    metrics = generate_weekly_report.extract_metrics_from_dailies(mock_dailies)
    assert "**2023-01-01**" in metrics
    assert "- Metric A: 10" in metrics
    assert "**2023-01-02**" in metrics
    assert "- Metric A: 12" in metrics


def test_git_activity_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = (
            "abc1234 Fix bug (Alice)\ndef5678 Add feature (Bob)"
        )
        log = generate_weekly_report.get_git_activity()
        assert "Fix bug" in log
        assert "Alice" in log


def test_git_activity_failure():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        log = generate_weekly_report.get_git_activity()
        assert "not found" in log


def test_build_user_prompt(mock_dailies):
    start = dt.date(2023, 1, 1)
    end = dt.date(2023, 1, 7)

    with patch("generate_weekly_report.get_git_activity", return_value="Mock Git Log"):
        prompt = generate_weekly_report.build_user_prompt(
            mock_dailies, start, end, "2023-W01"
        )

        assert "Week: 2023-W01" in prompt
        assert "### Aggregated Metrics" in prompt
        assert "- Metric A: 10" in prompt
        assert "### Git Activity" in prompt
        assert "Mock Git Log" in prompt
        assert "File: 2023-01-01-note.md" in prompt
