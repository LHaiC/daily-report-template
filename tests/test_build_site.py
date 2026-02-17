import os
import sys
import pytest
from pathlib import Path
import json
import datetime as dt

# Add scripts to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_site


@pytest.fixture
def mock_content(tmp_path):
    # Setup directories
    daily_dir = tmp_path / "content/daily"
    daily_dir.mkdir(parents=True)
    site_dir = tmp_path / "site"
    site_dir.mkdir(parents=True)

    # Override global constants for testing
    build_site.DAILY_ROOT = daily_dir
    build_site.SITE_ROOT = site_dir
    build_site.WEEKLY_ROOT = tmp_path / "content/weekly"

    # Create a dummy daily file with tags
    d1 = daily_dir / "2023-01-01-day-one.md"
    d1.write_text("""---
title: "First Day"
tags: ["python", "testing"]
---
# Content
""")

    d2 = daily_dir / "2023-01-02-day-two.md"
    d2.write_text("""---
title: "Second Day"
tags: ["python"]
---
# Content
""")

    return tmp_path


def test_parse_tags(mock_content):
    daily_dir = build_site.DAILY_ROOT
    entry = build_site.parse_daily_entry(daily_dir / "2023-01-01-day-one.md")

    assert entry["title"] == "First Day"
    assert "python" in entry["tags"]
    assert "testing" in entry["tags"]


def test_search_index_generation(mock_content):
    # Run the main build process
    build_site.main()

    search_json_path = build_site.SITE_ROOT / "search.json"
    assert search_json_path.exists()

    data = json.loads(search_json_path.read_text())
    assert len(data) == 2

    # Check first entry
    item = next(x for x in data if x["date"] == "2023-01-01")
    assert item["title"] == "First Day"
    assert "testing" in item["tags"]
    assert "/daily/2023/01/2023-01-01-day-one.html" in item["url"]


def test_tag_page_generation(mock_content):
    build_site.main()

    tags_dir = build_site.SITE_ROOT / "tags"
    assert tags_dir.exists()

    # Python tag page should exist (used in both files)
    python_page = tags_dir / "python.html"
    assert python_page.exists()
    content = python_page.read_text()
    assert "Tag: python" in content
    assert "First Day" in content
    assert "Second Day" in content

    # Testing tag page should exist (used in one file)
    testing_page = tags_dir / "testing.html"
    assert testing_page.exists()
    content = testing_page.read_text()
    assert "First Day" in content
    assert "Second Day" not in content
