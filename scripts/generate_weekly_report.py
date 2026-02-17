#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import re
import sys
import subprocess
from typing import Dict, List, Optional, Tuple

from generate_report import call_cloud_api, getenv


DEFAULT_WEEKLY_SYSTEM_PROMPT = """You are a rigorous technical writing assistant.
Summarize one week of daily reports and git activity into a concise weekly report in Markdown.

Output requirements:
1) Use this exact section order:
   - ## Weekly Highlights
   - ## Progress by Area
   - ## Problems / Blockers
   - ## Risks
   - ## Key Learnings
   - ## Next Week Plan
   - ## Metrics
2) Keep it concise and factual.
3) In the '## Metrics' section, consolidate the provided daily metrics into a summary table or list.
4) If information is missing, write "N/A" for that bullet.
5) Return only final answer. Do not include reasoning or thinking process.
"""


DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")


def parse_day_from_filename(path: Path) -> Optional[dt.date]:
    m = DATE_RE.match(path.name)
    if not m:
        return None
    return dt.date.fromisoformat(m.group(1))


def parse_weekday(value: str) -> Optional[int]:
    if not value:
        return None
    value = value.strip().lower()
    mapping = {
        "mon": 1,
        "monday": 1,
        "tue": 2,
        "tues": 2,
        "tuesday": 2,
        "wed": 3,
        "wednesday": 3,
        "thu": 4,
        "thurs": 4,
        "thursday": 4,
        "fri": 5,
        "friday": 5,
        "sat": 6,
        "saturday": 6,
        "sun": 7,
        "sunday": 7,
    }
    if value.isdigit():
        num = int(value)
        if 0 <= num <= 6:
            return num + 1
        if 1 <= num <= 7:
            return num
    return mapping.get(value)


def should_run_now() -> bool:
    if getenv("REPORT_WEEKLY_ENFORCE_SCHEDULE", "false").lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True

    now = dt.datetime.now(dt.timezone.utc)
    day = parse_weekday(getenv("REPORT_WEEKLY_DAY", "mon"))
    hour = getenv("REPORT_WEEKLY_HOUR_UTC", "9")

    if day is None:
        return False
    if hour and int(hour) != now.hour:
        return False
    return now.isoweekday() == day


def week_range(target_date: dt.date) -> Tuple[dt.date, dt.date]:
    weekday = target_date.isoweekday()
    start = target_date - dt.timedelta(days=weekday - 1)
    end = start + dt.timedelta(days=6)
    return start, end


def collect_daily_reports(start: dt.date, end: dt.date) -> List[Path]:
    root = Path("content/daily")
    if not root.exists():
        return []
    paths = []
    # Use rglob to search recursively in all subdirectories
    for path in root.rglob("*.md"):
        day = parse_day_from_filename(path)
        # Assuming parse_day_from_filename returns a date object or None
        if day and start <= day <= end:
            paths.append(path)
    return sorted(paths)


def extract_metrics_from_dailies(entries: List[Path]) -> str:
    """Extracts '## Metrics' sections from daily reports."""
    aggregated_metrics = []

    for path in entries:
        content = path.read_text(encoding="utf-8")
        # Look for ## Metrics until the next ## Header or End of String
        match = re.search(r"## Metrics\s*\n(.*?)(?=\n##|$)", content, re.DOTALL)
        if match:
            metrics_text = match.group(1).strip()
            if metrics_text and "N/A" not in metrics_text:
                day_str = parse_day_from_filename(path)
                aggregated_metrics.append(f"**{day_str}**:\n{metrics_text}")

    if not aggregated_metrics:
        return "No specific metrics found in daily reports."

    return "\n\n".join(aggregated_metrics)


def get_git_activity(days: int = 7) -> str:
    """Fetches git log for the last N days."""
    try:
        # Get short hash, commit message, and author name
        cmd = [
            "git",
            "log",
            f"--since={days} days ago",
            "--pretty=format:%h %s (%an)",
            "--no-merges",  # Optional: hide merge commits to reduce noise
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "Error fetching git activity (is this a git repo?)"
    except FileNotFoundError:
        return "git command not found."


def build_user_prompt(
    entries: List[Path], start: dt.date, end: dt.date, week_slug: str
) -> str:
    metrics_summary = extract_metrics_from_dailies(entries)
    git_log = get_git_activity(days=7)  # Approx 7 days

    parts = [
        f"Week: {week_slug}",
        f"Range: {start.isoformat()} to {end.isoformat()}",
        "",
        "### Aggregated Metrics from Daily Reports",
        metrics_summary,
        "",
        "### Git Activity (Commit Log)",
        git_log if git_log else "No recent git activity.",
        "",
        "### Daily Reports Content:",
    ]
    for path in entries:
        text = path.read_text(encoding="utf-8")
        parts.append(f"\n---\nFile: {path.name}\n{text}\n")

    parts.append("\nPlease generate a structured weekly report in Markdown.")
    parts.append(
        f"Add a title line at top: '# Weekly Report - {week_slug} ({start.isoformat()} to {end.isoformat()})'."
    )
    parts.append("Use the required section order exactly.")
    parts.append("Use bullet lists in each section.")

    return "\n".join(parts)


def ensure_minimum_sections(
    text: str, week_slug: str, start: dt.date, end: dt.date
) -> str:
    required = [
        "## Weekly Highlights",
        "## Progress by Area",
        "## Problems / Blockers",
        "## Risks",
        "## Key Learnings",
        "## Next Week Plan",
        "## Metrics",
    ]
    if all(sec in text for sec in required):
        return text

    return f"""# Weekly Report - {week_slug} ({start.isoformat()} to {end.isoformat()})

## Weekly Highlights
- N/A

## Progress by Area
- N/A

## Problems / Blockers
- N/A

## Risks
- N/A

## Key Learnings
- N/A

## Next Week Plan
- N/A

## Metrics
- N/A

---

### Raw Model Output
{text}
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate structured weekly report from daily reports using cloud API."
    )
    parser.add_argument("--output", required=True, help="Output markdown path")
    args = parser.parse_args()

    if not should_run_now():
        print("Weekly schedule not matched. Skipping.")
        return 0

    today = dt.date.today()
    include_today = getenv("REPORT_WEEKLY_INCLUDE_TODAY", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    end = today if include_today else today - dt.timedelta(days=1)
    start = end - dt.timedelta(days=6)
    week_slug = f"{start.isocalendar().year}-W{start.isocalendar().week:02d}"

    entries = collect_daily_reports(start, end)
    if not entries:
        print(f"No daily reports found for week {week_slug}")
        return 0

    system_prompt = getenv("REPORT_WEEKLY_SYSTEM_PROMPT", DEFAULT_WEEKLY_SYSTEM_PROMPT)
    user_prompt = build_user_prompt(entries, start, end, week_slug)
    text = call_cloud_api(user_prompt=user_prompt, system_prompt=system_prompt)
    text = ensure_minimum_sections(text, week_slug, start, end)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
    print(f"Wrote weekly report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
