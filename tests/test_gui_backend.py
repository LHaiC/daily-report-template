import os
import sys
import pytest
import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add gui to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "gui"))
import backend


@pytest.fixture
def mock_repo(tmp_path):
    # Create required directories
    (tmp_path / "content/daily").mkdir(parents=True)
    (tmp_path / "scratch").mkdir(parents=True)
    (tmp_path / "assets").mkdir(parents=True)
    (tmp_path / "scripts").mkdir(parents=True)

    # Create dummy generate script
    (tmp_path / "scripts/generate_report.py").write_text(
        "print('Mock Report Generated')"
    )

    return tmp_path


def test_ensure_today_note(mock_repo):
    manager = backend.NoteManager(mock_repo)
    note_path = manager.ensure_today_note()

    expected_name = f"{dt.date.today().isoformat()}.md"
    assert note_path.name == expected_name
    assert note_path.exists()
    assert "# Notes for" in note_path.read_text()


def test_generate_report_call(mock_repo):
    manager = backend.NoteManager(mock_repo)
    manager.ensure_today_note()

    # Mock subprocess.run
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Success"

        output = manager.generate_report()

        assert output == "Success"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "generate_report.py" in args[1]
