import os
import sys
import datetime as dt
import shutil
import pathlib
import uuid
import subprocess
import logging

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class NoteManager:
    def __init__(self, repo_root: str):
        self.repo_root = pathlib.Path(repo_root).resolve()
        self.daily_dir = self.repo_root / "content" / "daily"
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
        """Standard sync workflow: Pull -> Add -> Commit -> Push."""
        logger.info("Syncing repository...")
        self.run_git_command(["pull", "--rebase"])
        self.run_git_command(["add", "."])

        status = self.run_git_command(["status", "--porcelain"])
        if not status:
            logger.info("Nothing to commit.")
            return "No changes."

        today = dt.date.today().isoformat()
        self.run_git_command(["commit", "-m", f"chore: update notes for {today}"])
        self.run_git_command(["push"])
        logger.info("Sync complete.")
        return "Synced successfully."

    def generate_report(self, date_str: str = None):
        """
        Calls the existing scripts/generate_report.py logic.
        Passes the current scratch file as input.
        """
        if not date_str:
            date_str = dt.date.today().isoformat()

        script_path = self.repo_root / "scripts" / "generate_report.py"
        input_path = self.scratch_dir / f"{date_str}.md"
        # Output to content/daily/...
        # Note: The script handles directory creation and naming logic internally based on slug
        # We just need to give it a sensible default output path

        # Construct a default output path just to satisfy argparse requirement
        # The script's slug logic will likely rename it anyway
        output_dir = (
            self.daily_dir / str(dt.date.today().year) / str(dt.date.today().month)
        )
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

        logger.info(f"Generating report: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, cwd=str(self.repo_root), capture_output=True, text=True
        )

        if result.returncode != 0:
            logger.error(f"Generation Failed: {result.stderr}")
            raise RuntimeError(f"Report generation failed:\n{result.stderr}")

        logger.info(f"Generation Output: {result.stdout}")
        return result.stdout
