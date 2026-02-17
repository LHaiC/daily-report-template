import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# Add scripts to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
import manage_env
import generate_report


@pytest.fixture
def mock_env_file(tmp_path):
    # Override ENV_FILE in manage_env to a temp file
    p = tmp_path / ".env.test"
    manage_env.ENV_FILE = p
    return p


def test_load_save_env(mock_env_file):
    # Test saving
    manage_env.save_env("TEST_KEY", "test_value")

    assert mock_env_file.exists()
    content = json.loads(mock_env_file.read_text())
    assert content["TEST_KEY"] == "test_value"

    # Test loading
    loaded = manage_env.load_env()
    assert loaded["TEST_KEY"] == "test_value"


def test_get_env_priority(mock_env_file):
    # Set a system env var
    with patch.dict(os.environ, {"PRIORITY_TEST": "system_value"}):
        # 1. Default priority (System)
        assert manage_env.get_env("PRIORITY_TEST") == "system_value"

        # 2. Local override
        manage_env.save_env("PRIORITY_TEST", "local_value")
        assert manage_env.get_env("PRIORITY_TEST") == "local_value"


def test_generate_report_uses_manager(mock_env_file):
    # Set a secret key in local file
    manage_env.save_env("REPORT_API_KEY", "secret_key_123")

    # generate_report.getenv should now return this
    assert generate_report.getenv("REPORT_API_KEY") == "secret_key_123"
