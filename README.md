# Auto-Daily-Report

Turn raw daily notes into structured reports automatically.

Auto-Daily-Report is a GitHub template repo for technical journaling. It converts rough notes
into structured daily reports using a cloud LLM, keeps a weekly archive, and builds a static
site for browsing.

---

## What this product does

- **Two update paths**: local-first (commit `scratch/`) or web-first (labeled issues)
- **Auto-structured reports**: generated into `content/daily/YYYY/MM/`
- **Weekly summaries**: optional scheduled LLM summary in `content/weekly/`
- **Static site**: local preview or deploy to GitHub Pages
- **Idempotent by hash**: avoids re-processing unchanged notes

---

## Quick start

1. Click **Use this template** on GitHub.
2. Create a **private** repo.
3. Configure the `report-gen` environment (details below).

---

## Three ways to update your daily report

### Mode A (Local-first): commit scratch notes

1. Add/Rename/Modify notes under `scratch/`
2. Commit and push to `main`
3. Workflow `generate-from-commit.yml` generates reports into `content/daily/YYYY/MM/`

**Notes**
- Added, modified, and renamed files trigger generation.
- Deleting scratch files does not trigger generation.
- Hash-based idempotency prevents re-processing unchanged content.

### Mode B (Web-first): open a labeled issue

1. Create an issue from the **Raw Note** template (or manually)
2. Add the label `raw-note`
3. Workflow `generate-from-issue.yml`:
   - writes `scratch/issue-<num>.md`
   - generates `content/daily/YYYY/MM/YYYY-MM-DD-<slug>.md`
   - comments back on the issue

### Mode C (GUI): run the local desktop client

1. Install GUI dependencies (see below)
2. Run `python gui/main.py`
3. Use the editor to write notes and generate reports

---

## Environment setup (required)

Create the environment: `report-gen`

`Settings -> Environments -> New environment -> report-gen`

### Secrets

| Variable | Description |
|----------|-------------|
| `REPORT_API_KEY` | Your cloud LLM API key. |

### Variables (required)

| Variable | Example | Description |
|----------|---------|-------------|
| `REPORT_API_URL` | `https://integrate.api.nvidia.com/v1/chat/completions` | API endpoint URL. |
| `REPORT_API_MODEL` | `deepseek-ai/deepseek-v3.2` | Model identifier sent in the request body. |

### Variables (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `REPORT_API_AUTH_HEADER` | `Authorization` | HTTP header name for the API key. |
| `REPORT_API_AUTH_SCHEME` | `Bearer` | Auth scheme prefix. Set to empty string to send raw key. |
| `REPORT_API_TIMEOUT` | `120` | Request timeout in seconds. |
| `REPORT_SYSTEM_PROMPT` | *(built-in prompt)* | Override the default system prompt. |
| `REPORT_API_RESPONSE_PATH` | `choices.0.message.content` | Dotted path to extract text from JSON response. |
| `REPORT_API_RESPONSE_PATHS` | *(empty)* | Comma-separated list of dotted paths to try. Takes precedence over `REPORT_API_RESPONSE_PATH`. |
| `REPORT_STRIP_THINK` | `true` | Strip reasoning blocks from model output. |
| `REPORT_API_EXTRA_HEADERS_JSON` | *(empty)* | JSON dict of extra HTTP headers. |
| `REPORT_API_REQUEST_TEMPLATE_JSON` | *(empty)* | Custom JSON request template. |

When no custom request template is set, the default OpenAI-compatible chat format is used.

---

## Weekly summary (optional)

The scheduled workflow writes:

`content/weekly/YYYY/YYYY-WW-summary.md`

Environment variables (set in `report-gen`):

| Variable | Example | Description |
|----------|---------|-------------|
| `REPORT_WEEKLY_DAY` | `mon` | Weekday to run (mon..sun or 1..7). |
| `REPORT_WEEKLY_HOUR_UTC` | `9` | Hour in UTC to run. |
| `REPORT_WEEKLY_INCLUDE_TODAY` | `false` | Include today in the 7-day window. |
| `REPORT_WEEKLY_SYSTEM_PROMPT` | *(optional)* | Custom system prompt for weekly summary. |

Workflow file: `.github/workflows/generate-weekly-summary.yml`

---

## Static site

Build local HTML output:

```bash
python scripts/build_site.py
```

Local preview:

```bash
python -m http.server -d site 8000
```

Open: `http://localhost:8000`

---

## Hash index (idempotency)

The generator maintains a per-month hash index at:

`content/daily/YYYY/MM/.report_hashes.json`

Workflows skip re-processing when the `input_hash` already exists in the index. If the
index is missing, the scripts fall back to scanning frontmatter in existing reports.

---

## Repo rename (Auto-Daily-Report)

If you renamed the GitHub repository to `Auto-Daily-Report`, update your local remote:

```bash
git remote set-url origin git@github.com:<YOUR_USER_OR_ORG>/Auto-Daily-Report.git
git remote -v
```

HTTPS alternative:

```bash
git remote set-url origin https://github.com/<YOUR_USER_OR_ORG>/Auto-Daily-Report.git
git remote -v
```

---

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Local run (real API call):

```bash
export REPORT_API_URL="https://api.example.com/v1/chat/completions"
export REPORT_API_KEY="your-key"
export REPORT_API_MODEL="your-model"

python scripts/generate_report.py \
  --input scratch/example.md \
  --output content/daily/$(date +%Y)/$(date +%m)/$(date +%F)-example.md \
  --source-type manual \
  --source-id local
```

CLI arguments:

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--input` | yes | | Path to rough note file. |
| `--output` | yes | | Output markdown path. |
| `--date` | no | today's date | ISO date string (YYYY-MM-DD). |
| `--source-type` | no | `manual` | One of `manual`, `commit`, `issue`. |
| `--source-id` | no | `local` | Free-form source identifier. |
| `--force` | no | `false` | Force regeneration even if hash matches. |

---

## GUI (Windows/local)

The GUI client is cross-platform and tested on Windows/macOS/Linux. It supports
live Markdown preview and a local settings dialog for secrets.

### Install (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r gui/requirements.txt
```

### Run

```powershell
python gui\main.py
```

### Test the GUI backend

```powershell
python -m pytest tests\test_gui_backend.py
```

---

## Testing

```bash
# Run all tests
pytest -q

# Run a single test file
pytest -q tests/test_generate_report.py

# Run a single test by name
pytest -q tests/test_generate_report.py::test_call_cloud_api_default_openai

# Verbose output
pytest -vv
```

All tests mock `urllib.request.urlopen` -- no real network calls are made.

---

## File layout

```text
.
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── daily-report.yml
│   │   └── raw-note.yml
│   └── workflows/
│       ├── cleanup-scratch.yml
│       ├── generate-from-commit.yml
│       ├── generate-from-issue.yml
│       ├── generate-weekly-summary.yml
│       └── test.yml
├── content/
│   ├── daily/
│   │   └── YYYY/
│   │       └── MM/
│   │           ├── YYYY-MM-DD-<slug>.md
│   │           └── .report_hashes.json
│   └── weekly/
│       └── YYYY/
│           ├── YYYY-WW.md
│           └── YYYY-WW-summary.md
├── gui/
│   ├── main.py
│   ├── backend.py
│   └── requirements.txt
├── scratch/
├── scripts/
│   ├── build_site.py
│   ├── cleanup_scratch.py
│   ├── generate_report.py
│   ├── generate_weekly_report.py
│   └── manage_env.py
├── site/
│   └── assets/style.css
├── tests/
│   ├── conftest.py
│   └── test_*.py
├── AGENTS.md
├── requirements-dev.txt
└── README.md
```

---

## Notes

- Generated reports are committed by `github-actions[bot]`.
- Workflows use `environment: report-gen` so env vars/secrets are loaded from that environment.
- For private repositories, ensure your plan supports environments.
