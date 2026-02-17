"""
Build weekly archive markdown and a lightweight static site.

Outputs:
- content/weekly/YYYY/YYYY-WW.md
- site/index.html
- site/daily/YYYY/MM/YYYY-MM-DD-<slug>.html
- site/weekly/YYYY/YYYY-WW.html
"""

from __future__ import annotations

import datetime as dt
import html
import os
from pathlib import Path
import re
from typing import Iterable, List, Dict, Any


DAILY_ROOT = Path("content/daily")
WEEKLY_ROOT = Path("content/weekly")
SITE_ROOT = Path("site")

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")
WEEKLY_SUMMARY_RE = re.compile(r"^(\d{4}-W\d{2})-summary\.md$")


def iter_daily_files() -> Iterable[Path]:
    if not DAILY_ROOT.exists():
        return []
    return sorted(DAILY_ROOT.rglob("*.md"))


def parse_daily_entry(path: Path) -> Dict[str, Any]:
    m = DATE_RE.match(path.name)
    if not m:
        raise ValueError(f"Unexpected daily filename: {path}")
    date_str, slug = m.group(1), m.group(2)
    date = dt.date.fromisoformat(date_str)
    title = slug.replace("-", " ").strip()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
    except FileNotFoundError:
        pass
    iso_year, iso_week, _ = date.isocalendar()
    return {
        "date": date,
        "date_str": date_str,
        "slug": slug,
        "title": title,
        "path": path,
        "iso_year": iso_year,
        "iso_week": iso_week,
    }


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def weekly_markdown(
    entries: List[Dict[str, Any]], week_year: int, week_num: int
) -> str:
    header = f"# Weekly Report - {week_year}-W{week_num:02d}"
    lines = [header, "", "## Days"]
    for e in entries:
        daily_rel = os.path.relpath(e["path"], start=WEEKLY_ROOT / str(week_year))
        lines.append(f"- {e['date_str']} - [{e['title']}]({daily_rel})")
    return "\n".join(lines) + "\n"


def build_weekly_archive(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    weekly_entries: List[Dict[str, Any]] = []
    grouped: Dict[tuple, List[Dict[str, Any]]] = {}
    for e in entries:
        key = (e["iso_year"], e["iso_week"])
        grouped.setdefault(key, []).append(e)
    for (week_year, week_num), items in sorted(grouped.items()):
        items = sorted(items, key=lambda x: x["date"])
        out_dir = WEEKLY_ROOT / str(week_year)
        ensure_dir(out_dir)
        out_path = out_dir / f"{week_year}-W{week_num:02d}.md"
        out_path.write_text(
            weekly_markdown(items, week_year, week_num), encoding="utf-8"
        )
        weekly_entries.append(
            {
                "week_year": week_year,
                "week_num": week_num,
                "path": out_path,
                "entries": items,
            }
        )
    return weekly_entries


def markdown_to_html(text: str) -> str:
    lines = text.splitlines()
    out: List[str] = []
    in_code = False
    in_list = False
    paragraph: List[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            out.append("<p>" + "<br>".join(paragraph) + "</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for line in lines:
        if line.startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                flush_paragraph()
                close_list()
                lang = line[3:].strip()
                class_attr = f' class="language-{html.escape(lang)}"' if lang else ""
                out.append(f"<pre><code{class_attr}>")
                in_code = True
            continue

        if in_code:
            out.append(html.escape(line))
            continue

        if not line.strip():
            flush_paragraph()
            close_list()
            continue

        if line.startswith("# "):
            flush_paragraph()
            close_list()
            out.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
            continue
        if line.startswith("## "):
            flush_paragraph()
            close_list()
            out.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
            continue
        if line.startswith("### "):
            flush_paragraph()
            close_list()
            out.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
            continue
        if line.startswith("- "):
            flush_paragraph()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{html.escape(line[2:].strip())}</li>")
            continue

        paragraph.append(html.escape(line.strip()))

    flush_paragraph()
    close_list()
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def page_template(title: str, body: str) -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <link rel="stylesheet" href="/assets/style.css" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div class="bg"></div>
    <header class="site-header">
      <div class="brand">
        <div class="brand-mark"></div>
        <div class="brand-text">
          <div class="brand-title">Tech Journal</div>
          <div class="brand-sub">Structured daily reports</div>
        </div>
      </div>
      <nav class="nav">
        <a href="/index.html">Latest</a>
        <a href="/weekly/index.html">Weekly</a>
      </nav>
    </header>
    <main class="container">
      {body}
    </main>
    <footer class="site-footer">Generated by build_site.py</footer>
  </body>
</html>
""".format(title=html.escape(title), body=body)


def build_daily_pages(entries: List[Dict[str, Any]]) -> None:
    for e in entries:
        out_dir = (
            SITE_ROOT / "daily" / e["date"].strftime("%Y") / e["date"].strftime("%m")
        )
        ensure_dir(out_dir)
        out_path = out_dir / (e["path"].stem + ".html")
        text = e["path"].read_text(encoding="utf-8")
        content = markdown_to_html(text)
        body = f'<article class="card">{content}</article>'
        out_path.write_text(page_template(e["title"], body), encoding="utf-8")


def collect_weekly_summaries() -> Dict[str, Path]:
    summaries: Dict[str, Path] = {}
    if not WEEKLY_ROOT.exists():
        return summaries
    for path in WEEKLY_ROOT.rglob("*-summary.md"):
        m = WEEKLY_SUMMARY_RE.match(path.name)
        if not m:
            continue
        summaries[m.group(1)] = path
    return summaries


def build_weekly_pages(
    weekly_entries: List[Dict[str, Any]], summary_paths: Dict[str, Path]
) -> None:
    weekly_index_items: List[str] = []
    for w in sorted(
        weekly_entries, key=lambda x: (x["week_year"], x["week_num"]), reverse=True
    ):
        week_slug = f"{w['week_year']}-W{w['week_num']:02d}"
        summary_path = summary_paths.get(week_slug)
        summary_link = (
            f'<a class="summary-link" href="/weekly/{w["week_year"]}/{week_slug}-summary.html">Summary</a>'
            if summary_path
            else ""
        )
        weekly_index_items.append(
            f'<li><a href="/weekly/{w["week_year"]}/{week_slug}.html">{week_slug}</a>'
            f'<span class="muted">{len(w["entries"])} days</span>{summary_link}</li>'
        )

        out_dir = SITE_ROOT / "weekly" / str(w["week_year"])
        ensure_dir(out_dir)
        out_path = out_dir / f"{week_slug}.html"

        items = []
        for e in sorted(w["entries"], key=lambda x: x["date"]):
            daily_href = "/daily/{}/{}.html".format(
                e["date"].strftime("%Y/%m"),
                e["path"].stem,
            )
            items.append(
                f'<li><a href="{daily_href}">{e["date_str"]}</a>'
                f'<span class="muted">{html.escape(e["title"])}</span></li>'
            )
        body = (
            f'<section class="card"><h1>{week_slug}</h1>'
            f'<ul class="list">{"".join(items)}</ul></section>'
        )
        out_path.write_text(page_template(week_slug, body), encoding="utf-8")

        if summary_path:
            summary_text = summary_path.read_text(encoding="utf-8")
            summary_body = (
                f'<article class="card">{markdown_to_html(summary_text)}</article>'
            )
            summary_out = out_dir / f"{week_slug}-summary.html"
            summary_out.write_text(
                page_template(f"{week_slug} Summary", summary_body), encoding="utf-8"
            )

    weekly_index = (
        '<section class="card">'
        "<h1>Weekly Archive</h1>"
        f'<ul class="list">{"".join(weekly_index_items)}</ul>'
        "</section>"
    )
    weekly_index_path = SITE_ROOT / "weekly" / "index.html"
    ensure_dir(weekly_index_path.parent)
    weekly_index_path.write_text(
        page_template("Weekly Archive", weekly_index), encoding="utf-8"
    )


def build_index(
    entries: List[Dict[str, Any]],
    weekly_entries: List[Dict[str, Any]],
    summary_paths: Dict[str, Path],
) -> None:
    latest = sorted(entries, key=lambda x: x["date"], reverse=True)[:30]
    daily_items = []
    for e in latest:
        daily_href = "/daily/{}/{}.html".format(
            e["date"].strftime("%Y/%m"),
            e["path"].stem,
        )
        daily_items.append(
            f'<li><a href="{daily_href}">{e["date_str"]}</a>'
            f'<span class="muted">{html.escape(e["title"])}</span></li>'
        )
    week_items = []
    for w in sorted(
        weekly_entries, key=lambda x: (x["week_year"], x["week_num"]), reverse=True
    )[:12]:
        week_slug = f"{w['week_year']}-W{w['week_num']:02d}"
        summary_path = summary_paths.get(week_slug)
        summary_link = (
            f'<a class="summary-link" href="/weekly/{w["week_year"]}/{week_slug}-summary.html">Summary</a>'
            if summary_path
            else ""
        )
        week_items.append(
            f'<li><a href="/weekly/{w["week_year"]}/{week_slug}.html">{week_slug}</a>'
            f'<span class="muted">{len(w["entries"])} days</span>{summary_link}</li>'
        )

    body = """<section class="hero">
  <div>
    <h1>Daily Reports</h1>
    <p>Latest structured reports and weekly rollups.</p>
  </div>
  <div class="hero-meta">Updated: {updated}</div>
</section>
<section class="grid">
  <div class="card">
    <h2>Latest Entries</h2>
    <ul class="list">{daily_items}</ul>
  </div>
  <div class="card">
    <h2>Weekly Archive</h2>
    <ul class="list">{week_items}</ul>
  </div>
</section>
""".format(
        updated=dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        daily_items="".join(daily_items),
        week_items="".join(week_items),
    )
    ensure_dir(SITE_ROOT)
    (SITE_ROOT / "index.html").write_text(
        page_template("Daily Reports", body), encoding="utf-8"
    )


def main() -> int:
    entries: List[Dict[str, Any]] = []
    for path in iter_daily_files():
        try:
            entries.append(parse_daily_entry(path))
        except ValueError:
            continue

    if not entries:
        return 0

    ensure_dir(WEEKLY_ROOT)
    ensure_dir(SITE_ROOT / "assets")

    weekly_entries = build_weekly_archive(entries)
    summary_paths = collect_weekly_summaries()
    build_daily_pages(entries)
    build_weekly_pages(weekly_entries, summary_paths)
    build_index(entries, weekly_entries, summary_paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
