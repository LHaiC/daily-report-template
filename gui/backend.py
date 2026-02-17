import os
import sys
import datetime as dt
import shutil
import pathlib
import uuid
import subprocess
import logging
import json
import re
from typing import List, Dict, Optional, Tuple

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class NoteManager:
    def __init__(self, repo_root: str):
        self.repo_root = pathlib.Path(repo_root).resolve()
        self.daily_dir = self.repo_root / "content" / "daily"
        self.weekly_dir = self.repo_root / "content" / "weekly"
        self.scratch_dir = self.repo_root / "scratch"
        # Ensure base directories exist
        self.scratch_dir.mkdir(parents=True, exist_ok=True)

    def get_today_note_path(self) -> pathlib.Path:
        """Returns path to today's scratch note (YYYY-MM-DD.md)."""
        today = dt.date.today().isoformat()
        return self.scratch_dir / f"{today}.md"

    def ensure_today_note(self) -> pathlib.Path:
        """Creates today's note if it doesn't exist."""
        path = self.get_today_note_path()
        if not path.exists():
            path.write_text(
                f"# Notes for {dt.date.today().isoformat()}\n\n", encoding="utf-8"
            )
        return path

    def create_scratch_note(self, name: str, date_str: str = None) -> pathlib.Path:
        """Create a new scratch note with custom name and date."""
        if not date_str:
            date_str = dt.date.today().isoformat()

        # Sanitize filename
        safe_name = re.sub(r'[^\w\s-]', '', name).strip()
        safe_name = re.sub(r'[-\s]+', '-', safe_name)

        filename = f"{date_str}-{safe_name}.md"
        path = self.scratch_dir / filename

        if path.exists():
            raise FileExistsError(f"File {filename} already exists")

        content = f"""# {name}

Date: {date_str}

## Rough Notes

"""
        path.write_text(content, encoding="utf-8")
        return path

    def list_scratch_files(self) -> List[Dict]:
        """List all scratch files with metadata."""
        files = []
        for path in sorted(self.scratch_dir.glob("*.md"), reverse=True):
            if path.name == ".gitkeep":
                continue
            stat = path.stat()
            files.append({
                "path": path,
                "name": path.stem,
                "modified": dt.datetime.fromtimestamp(stat.st_mtime),
                "size": stat.st_size,
            })
        return files

    def list_daily_reports(self) -> List[Dict]:
        """List all generated daily reports with metadata."""
        reports = []
        if not self.daily_dir.exists():
            return reports

        for path in sorted(self.daily_dir.rglob("*.md"), reverse=True):
            if path.name.startswith("."):
                continue

            # Parse frontmatter
            meta = self._parse_frontmatter(path)

            stat = path.stat()
            reports.append({
                "path": path,
                "name": path.stem,
                "title": meta.get("title", path.stem),
                "tags": meta.get("tags", []),
                "date": meta.get("date", ""),
                "input_hash": meta.get("input_hash", ""),
                "modified": dt.datetime.fromtimestamp(stat.st_mtime),
                "size": stat.st_size,
            })
        return reports

    def list_weekly_reports(self) -> List[Dict]:
        """List all weekly reports."""
        reports = []
        if not self.weekly_dir.exists():
            return reports

        for path in sorted(self.weekly_dir.rglob("*.md"), reverse=True):
            if path.name.startswith("."):
                continue

            stat = path.stat()
            reports.append({
                "path": path,
                "name": path.stem,
                "modified": dt.datetime.fromtimestamp(stat.mtime),
                "size": stat.st_size,
            })
        return reports

    def _parse_frontmatter(self, path: pathlib.Path) -> Dict:
        """Parse YAML frontmatter from a markdown file."""
        try:
            text = path.read_text(encoding="utf-8")
            lines = text.lstrip().splitlines()
            if len(lines) < 3 or lines[0].strip() != "---":
                return {}

            data = {}
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                if ":" not in line:
                    continue
                key, val = line.split(":", 1)
                key = key.strip().lower()
                val = val.strip().strip('"').strip("'")

                if key == "tags":
                    # Parse tags array
                    val = val.strip("[]")
                    data[key] = [t.strip().strip('"').strip("'") for t in val.split(",") if t.strip()]
                else:
                    data[key] = val
            return data
        except Exception:
            return {}

    def delete_report(self, path: pathlib.Path) -> bool:
        """Delete a report and remove its hash from the index."""
        try:
            # Get the input_hash before deleting
            meta = self._parse_frontmatter(path)
            input_hash = meta.get("input_hash", "")

            # Delete the file
            path.unlink()

            # Remove hash from index
            if input_hash:
                self._remove_hash_from_index(path.parent, input_hash)

            logger.info(f"Deleted report: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete report: {e}")
            return False

    def _remove_hash_from_index(self, daily_root: pathlib.Path, input_hash: str) -> None:
        """Remove a hash from the .report_hashes.json index."""
        index_path = daily_root / ".report_hashes.json"
        if not index_path.exists():
            return

        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                if input_hash in data:
                    data.remove(input_hash)
                    index_path.write_text(json.dumps(data), encoding="utf-8")
                    logger.info(f"Removed hash {input_hash[:8]}... from index")
            elif isinstance(data, dict):
                if input_hash in data:
                    del data[input_hash]
                    index_path.write_text(json.dumps(data), encoding="utf-8")
                    logger.info(f"Removed hash {input_hash[:8]}... from index")
        except Exception as e:
            logger.error(f"Failed to update hash index: {e}")

    def generate_weekly_summary(self, year: int = None, week: int = None) -> str:
        """Generate weekly summary report."""
        script_path = self.repo_root / "scripts" / "generate_weekly_report.py"

        if not script_path.exists():
            raise FileNotFoundError("Weekly report script not found")

        cmd = [sys.executable, str(script_path)]

        if year and week:
            cmd.extend(["--year", str(year), "--week", str(week)])

        logger.info(f"Generating weekly summary: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, cwd=str(self.repo_root), capture_output=True, text=True
        )

        if result.returncode != 0:
            logger.error(f"Weekly generation failed: {result.stderr}")
            raise RuntimeError(f"Weekly summary generation failed:\n{result.stderr}")

        logger.info(f"Weekly generation output: {result.stdout}")
        return result.stdout

    def run_git_command(self, args: list[str]) -> str:
        """Runs a git command in the repo root."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Git Error: {e.stderr}")
            raise RuntimeError(f"Git command failed: {e.stderr}")

    def sync(self):
        """Standard sync workflow: Add -> Commit -> Pull -> Push."""
        logger.info("Syncing repository...")

        # First, add all changes
        self.run_git_command(["add", "."])

        # Check if there are changes to commit
        status = self.run_git_command(["status", "--porcelain"])
        if status:
            # Commit local changes first
            today = dt.date.today().isoformat()
            self.run_git_command(["commit", "-m", f"chore: update notes for {today}"])

        # Now pull with rebase (no unstaged changes since we committed)
        try:
            self.run_git_command(["pull", "--rebase"])
        except RuntimeError as e:
            # If pull fails, we might need to abort and retry
            if "unstaged changes" in str(e).lower():
                logger.warning("Pull failed due to unstaged changes, stashing and retrying...")
                self.run_git_command(["stash", "push", "-m", "auto-stash-before-pull"])
                self.run_git_command(["pull", "--rebase"])
                self.run_git_command(["stash", "pop"])
            else:
                raise

        # Push changes
        self.run_git_command(["push"])
        logger.info("Sync complete.")
        return "Synced successfully." if status else "No local changes. Synced with remote."

    def generate_report(self, input_path: pathlib.Path = None, date_str: str = None, force: bool = False):
        """
        Calls the existing scripts/generate_report.py logic.
        Passes the current scratch file as input.
        """
        if not input_path:
            if not date_str:
                date_str = dt.date.today().isoformat()
            input_path = self.scratch_dir / f"{date_str}.md"

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        if not date_str:
            # Try to extract date from filename
            match = re.match(r'(\d{4}-\d{2}-\d{2})', input_path.name)
            if match:
                date_str = match.group(1)
            else:
                date_str = dt.date.today().isoformat()

        script_path = self.repo_root / "scripts" / "generate_report.py"
        output_dir = self.daily_dir / date_str[:4] / date_str[5:7]
        output_path = output_dir / f"{date_str}-generated.md"

        cmd = [
            sys.executable,
            str(script_path),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--date",
            date_str,
            "--source-type",
            "manual",
            "--source-id",
            "gui",
        ]

        if force:
            cmd.append("--force")

        logger.info(f"Generating report: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, cwd=str(self.repo_root), capture_output=True, text=True
        )

        if result.returncode != 0:
            logger.error(f"Generation Failed: {result.stderr}")
            raise RuntimeError(f"Report generation failed:\n{result.stderr}")

        logger.info(f"Generation Output: {result.stdout}")
        return result.stdout