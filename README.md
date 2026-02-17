# Tech Journal Template (Local Markdown + Auto Structured Daily Reports)

A **GitHub template repository** for technical journaling with a low-friction workflow:

- You write rough notes in `scratch/` (or open a labeled issue)
- GitHub Actions listens for `push` / `issues` events
- A Python script calls a **cloud LLM API** (configured via **Environment vars/secrets**)
- Structured daily report is generated to `content/daily/YYYY/MM/` (archived by year and month)
- Static site output (local preview + optional GitHub Pages) included

---

## 1) How to use this template

### A. Create your own private repo from this template
1. Click **Use this template** on GitHub.
2. Choose **Private** visibility.
3. Create repository.

### B. Enable this repository as a template (for maintainers)
`Settings -> General -> Template repository` (check it).

---

## 2) Setup required GitHub Environment

Create environment: `report-gen`

`Settings -> Environments -> New environment -> report-gen`

### Environment **Secrets**

| Variable | Description |
|----------|-------------|
| `REPORT_API_KEY` | Your cloud LLM API key. |

### Environment **Variables**

#### Required

| Variable | Example | Description |
|----------|---------|-------------|
| `REPORT_API_URL` | `https://integrate.api.nvidia.com/v1/chat/completions` | API endpoint URL. |
| `REPORT_API_MODEL` | `deepseek-ai/deepseek-v3.2` | Model identifier sent in the request body. Omitted from payload if empty. |

#### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `REPORT_API_AUTH_HEADER` | `Authorization` | HTTP header name for the API key. |
| `REPORT_API_AUTH_SCHEME` | `Bearer` | Auth scheme prefix. Set to empty string to send raw key. |
| `REPORT_API_TIMEOUT` | `120` | Request timeout in seconds. |
| `REPORT_SYSTEM_PROMPT` | *(built-in prompt)* | Override the default system prompt. |
| `REPORT_API_RESPONSE_PATH` | `choices.0.message.content` | Dotted path to extract text from the JSON response. |
| `REPORT_API_RESPONSE_PATHS` | *(empty)* | Comma-separated list of dotted paths to try (takes precedence over `REPORT_API_RESPONSE_PATH`). Built-in fallback paths are always appended. |
| `REPORT_STRIP_THINK` | `true` | Strip `<think>`/`<reasoning>` blocks and reasoning fenced blocks from model output. Accepts `true`/`1`/`yes`/`on`. |
| `REPORT_API_EXTRA_HEADERS_JSON` | *(empty)* | JSON dict of additional HTTP headers, e.g. `{"X-Custom": "val"}`. |
| `REPORT_API_REQUEST_TEMPLATE_JSON` | *(empty)* | Custom JSON request body template. Placeholders: `{{model}}`, `{{system_prompt}}`, `{{user_prompt}}`. When unset, the default OpenAI-compatible chat format is used. |

> **Note:** When no `REPORT_API_REQUEST_TEMPLATE_JSON` is set, the script sends
> an OpenAI-compatible chat completion request with `temperature=0.2`,
> `top_p=0.9`, `stream=false`.

---

## 3) Two ingestion modes

### Mode A: Commit rough notes
1. Add/Rename **new** rough markdown/txt notes into `scratch/`
2. Commit and push to `main`
3. Workflow `generate-from-commit.yml` runs and writes report to `content/daily/YYYY/MM/`

> **Note:** Only **newly added** files in `scratch/` trigger report generation.
> Editing or deleting existing scratch files does not trigger the workflow.

### Mode B: Open an issue as rough notes
1. Create issue from **Raw Note** template OR manually
2. Add label `raw-note`
3. Workflow `generate-from-issue.yml` runs:
   - writes `scratch/issue-<num>.md`
   - generates `content/daily/YYYY/MM/YYYY-MM-DD-issue-<num>.md`
   - comments back on the issue

---

## 4) Weekly archive + static site

Generate weekly rollups and a static HTML site:

```bash
python scripts/build_site.py
```

Outputs:

- Weekly markdown: `content/weekly/YYYY/YYYY-WW.md`
- Static site: `site/`

Local preview options:

```bash
python -m http.server -d site 8000
```

Then open `http://localhost:8000`.

To publish on GitHub Pages, point Pages to the `site/` folder or deploy it via a workflow.

## 5) Weekly LLM summary (scheduled)

This workflow summarizes the previous week using the same LLM backend and writes:

`content/weekly/YYYY/YYYY-WW-summary.md`

It runs hourly but only generates when the configured schedule matches.

Environment variables (set in `report-gen`):

| Variable | Example | Description |
|----------|---------|-------------|
| `REPORT_WEEKLY_DAY` | `mon` | Weekday to run (mon..sun or 1..7). |
| `REPORT_WEEKLY_HOUR_UTC` | `9` | Hour in UTC to run. |
| `REPORT_WEEKLY_INCLUDE_TODAY` | `false` | Include today's report in the 7-day window. |
| `REPORT_WEEKLY_SYSTEM_PROMPT` | *(optional)* | Custom system prompt for weekly summary. |

Workflow file: `.github/workflows/generate-weekly-summary.yml`

## 6) Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Local run (real API call)

Create a rough note file under `scratch/`, then run the generator with
the required environment variables set for your cloud API.

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

### CLI arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--input` | yes | | Path to rough note file. |
| `--output` | yes | | Output markdown path. |
| `--date` | no | today's date | ISO date string (YYYY-MM-DD). |
| `--source-type` | no | `manual` | One of `manual`, `commit`, `issue`. |
| `--source-id` | no | `local` | Free-form source identifier. |

---

## 7) Testing

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

CI workflow is in `.github/workflows/test.yml` (Python 3.11).

---

## 8) File layout

```text
.
├── .github/
│   ├── ISSUE_TEMPLATE/raw-note.yml
│   └── workflows/
│       ├── generate-from-commit.yml
│       ├── generate-from-issue.yml
│       ├── generate-weekly-summary.yml
│       └── test.yml
├── content/daily/
│   └── YYYY/
│       └── MM/
│           └── YYYY-MM-DD-<slug>.md
├── scratch/
├── scripts/generate_report.py
├── scripts/generate_weekly_report.py
├── tests/test_generate_report.py
├── requirements-dev.txt
└── README.md
```

---

## 9) Notes

- Generated reports are committed by `github-actions[bot]`.
- Workflow uses `environment: report-gen` so env vars/secrets are loaded from that environment.
- For private repositories, make sure your plan supports environments.
