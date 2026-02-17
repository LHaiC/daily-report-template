#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

# Import environment manager
try:
    import manage_env
except ImportError:
    # If not found (e.g. running in CI/Docker without full repo context?), create a dummy
    class manage_env:
        @staticmethod
        def get_env(key, default=None):
            return os.getenv(key, default)


DEFAULT_SYSTEM_PROMPT = """You are a rigorous technical writing assistant.
Turn rough notes into ONE structured daily report in Markdown with a YAML frontmatter block.

Output requirements:
1) Start with a YAML frontmatter block exactly like this:
---
title: "Short Summary Title"
slug: "short-summary-title"
tags: ["tag1", "tag2"]
status: "completed"
---

2) Follow with the report content using this exact section order:
   - ## What I Did Today
   - ## Problems / Blockers
   - ## Root Cause
   - ## Attempts & Fixes
   - ## Key Learnings
   - ## Metrics
   - ## Next Steps (Tomorrow)

3) Keep it concise and factual.
4) The 'slug' in frontmatter should be a URL-friendly version of the title (lowercase, dashes only).
5) If information is missing, write "N/A" for that bullet.
6) Return only final answer. Do not include reasoning or thinking process.
"""


def getenv(name: str, default: Optional[str] = None, required: bool = False) -> str:
    # Use manage_env to prioritize local secrets > os.environ
    value = manage_env.get_env(name, default)

    # Treat empty string as unset, use default
    if not value or value.strip() == "":
        value = default
    if required and (value is None or str(value).strip() == ""):
        raise RuntimeError(f"Missing required env var: {name}")
    return value or ""


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\-_\u4e00-\u9fff]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "note"


def normalize_tag(tag: str) -> str:
    tag = tag.strip().lower()
    tag = tag.lstrip("#")
    tag = re.sub(r"[^a-z0-9\-_\u4e00-\u9fff]+", "-", tag)
    tag = re.sub(r"-{2,}", "-", tag).strip("-")
    return tag


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_report_hash_index(daily_root: pathlib.Path) -> set[str]:
    index_path = daily_root / ".report_hashes.json"
    if not index_path.exists():
        return set()
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if isinstance(data, list):
        return {str(item) for item in data if item}
    if isinstance(data, dict):
        return {str(k) for k in data.keys()}
    return set()


def update_report_hash_index(daily_root: pathlib.Path, input_hash: str) -> None:
    daily_root.mkdir(parents=True, exist_ok=True)
    index_path = daily_root / ".report_hashes.json"
    hashes = load_report_hash_index(daily_root)
    hashes.add(input_hash)
    index_path.write_text(json.dumps(sorted(hashes)), encoding="utf-8")


def parse_frontmatter(text: str) -> Dict[str, str]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}
    data: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        data[key.strip().lower()] = val.strip()
    return data


def extract_frontmatter_block(text: str) -> tuple[Dict[str, str], str]:
    match = re.search(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}, text
    block = match.group(1)
    meta: Dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        meta[key.strip().lower()] = val.strip()
    stripped = text[match.end() :].lstrip()
    return meta, stripped


def strip_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1 :]).lstrip()
    return text


def extract_title_tags(text: str) -> tuple[str, list[str], str]:
    lines = text.splitlines()
    title = ""
    tags: list[str] = []
    cleaned: list[str] = []
    consumed = 0
    for line in lines[:6]:
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            consumed += 1
            continue
        if line.lower().startswith("tags:"):
            raw = line.split(":", 1)[1].strip()
            raw = raw.strip("[]")
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            tags = [normalize_tag(p) for p in parts if normalize_tag(p)]
            consumed += 1
            continue
        break
    if consumed:
        cleaned = lines[consumed:]
    else:
        cleaned = lines

    if not title:
        for line in cleaned:
            if line.startswith("# "):
                title = line[2:].strip()
                break
    if not tags:
        for line in cleaned[:12]:
            if line.lower().startswith("tags:"):
                raw = line.split(":", 1)[1].strip()
                raw = raw.strip("[]")
                parts = [p.strip() for p in raw.split(",") if p.strip()]
                tags = [normalize_tag(p) for p in parts if normalize_tag(p)]
                break
    tags = [t for t in tags if t]
    tags = sorted(set(tags))
    return title, tags, "\n".join(cleaned).lstrip()


def extract_by_path(data: Any, path: str) -> Any:
    """Extract value by dotted path, e.g. choices.0.message.content"""
    if not path:
        return data
    cur = data
    for part in path.split("."):
        if isinstance(cur, list):
            idx = int(part)
            cur = cur[idx]
        elif isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(f"Cannot navigate part={part!r} on type={type(cur)}")
    return cur


def replace_placeholders(obj: Any, mapping: Dict[str, str]) -> Any:
    if isinstance(obj, str):
        out = obj
        for k, v in mapping.items():
            out = out.replace("{{" + k + "}}", v)
        return out
    if isinstance(obj, list):
        return [replace_placeholders(x, mapping) for x in obj]
    if isinstance(obj, dict):
        return {k: replace_placeholders(v, mapping) for k, v in obj.items()}
    return obj


def build_default_payload(
    model: str, system_prompt: str, user_prompt: str
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model if model else None,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "stream": False,
    }
    if payload["model"] is None:
        payload.pop("model")
    return payload


def call_cloud_api(user_prompt: str, system_prompt: str) -> str:
    import re  # local import to keep this function self-contained

    api_url = getenv("REPORT_API_URL", required=True)
    api_key = getenv("REPORT_API_KEY", "")
    api_model = getenv("REPORT_API_MODEL", "")
    timeout = int(getenv("REPORT_API_TIMEOUT", "120"))

    # Backward compatible:
    # - New: REPORT_API_RESPONSE_PATHS (comma-separated)
    # - Old: REPORT_API_RESPONSE_PATH (single path)
    response_paths_csv = getenv("REPORT_API_RESPONSE_PATHS", "").strip()
    legacy_response_path = getenv(
        "REPORT_API_RESPONSE_PATH", "choices.0.message.content"
    ).strip()
    if not response_paths_csv:
        response_paths_csv = legacy_response_path

    auth_header = getenv("REPORT_API_AUTH_HEADER", "Authorization")
    auth_scheme = getenv("REPORT_API_AUTH_SCHEME", "Bearer")
    extra_headers_json = getenv("REPORT_API_EXTRA_HEADERS_JSON", "")
    request_template_json = getenv("REPORT_API_REQUEST_TEMPLATE_JSON", "")

    # Whether to strip think/reasoning blocks from final text
    strip_think = getenv("REPORT_STRIP_THINK", "true").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    def _extract_first_available(data, paths_csv: str):
        paths = [p.strip() for p in paths_csv.split(",") if p.strip()]
        # Add robust fallbacks (deduplicated, order-preserving)
        fallback_paths = [
            "choices.0.message.final",
            "choices.0.message.answer",
            "choices.0.message.content",
            "choices.0.text",
            "response.output_text",
            "output_text",
            "data.text",
            "text",
        ]
        for p in fallback_paths:
            if p not in paths:
                paths.append(p)

        last_err = None
        for p in paths:
            try:
                return extract_by_path(data, p)
            except Exception as e:
                last_err = e
                continue

        if last_err:
            raise RuntimeError(
                f"Unable to extract model output from response paths: {paths}. Last error: {last_err}"
            )
        raise RuntimeError("No response paths configured.")

    def _normalize_to_text(value):
        # Handle OpenAI-ish multimodal blocks / custom structures
        if isinstance(value, list):
            chunks = []
            for item in value:
                if isinstance(item, dict):
                    item_type = str(item.get("type", "")).lower()
                    # Skip explicit reasoning blocks when requested
                    if strip_think and item_type in {
                        "reasoning",
                        "thought",
                        "thinking",
                    }:
                        continue
                    if item_type == "text":
                        t = item.get("text", "")
                        if t:
                            chunks.append(str(t))
                    elif "text" in item:
                        chunks.append(str(item["text"]))
                    elif "content" in item:
                        chunks.append(str(item["content"]))
                else:
                    chunks.append(str(item))
            return "\n".join([c for c in chunks if c]).strip()

        if isinstance(value, dict):
            # Prefer final/answer-like fields first
            for k in ("final", "answer", "output_text", "text", "content"):
                if k in value and value[k] not in (None, ""):
                    return _normalize_to_text(value[k])

            # Common nested message format
            if "message" in value and value["message"] not in (None, ""):
                return _normalize_to_text(value["message"])

            # Last resort
            return json.dumps(value, ensure_ascii=False)

        return str(value).strip()

    def _strip_think_blocks(text: str) -> str:
        # Remove explicit think/reasoning wrappers and fenced blocks
        patterns = [
            r"<think>[\s\S]*?</think>",
            r"<reasoning>[\s\S]*?</reasoning>",
            r"```(?:think|thinking|reasoning)[\s\S]*?```",
        ]
        out = text
        for pat in patterns:
            out = re.sub(pat, "", out, flags=re.IGNORECASE)

        # Optional: remove leading "Reasoning:" / "Thought:" lines
        out = re.sub(r"(?im)^\s*(reasoning|thought|thinking)\s*:\s*.*$", "", out)

        # Collapse excessive blank lines
        out = re.sub(r"\n{3,}", "\n\n", out).strip()
        return out

    mapping = {
        "model": api_model,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }

    if request_template_json.strip():
        try:
            template = json.loads(request_template_json)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid REPORT_API_REQUEST_TEMPLATE_JSON: {e}") from e
        payload = replace_placeholders(template, mapping)
    else:
        payload = build_default_payload(api_model, system_prompt, user_prompt)

    headers = {"Content-Type": "application/json"}
    if api_key:
        token_val = f"{auth_scheme} {api_key}".strip() if auth_scheme else api_key
        headers[auth_header] = token_val

    if extra_headers_json.strip():
        try:
            headers.update(json.loads(extra_headers_json))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid REPORT_API_EXTRA_HEADERS_JSON: {e}") from e

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        raise RuntimeError(f"Cloud API HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cloud API request failed: {e}") from e

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Cloud API returned non-JSON response: {raw[:500]}") from e

    value = _extract_first_available(result, response_paths_csv)
    text = _normalize_to_text(value)

    if strip_think:
        text = _strip_think_blocks(text)

    if not text:
        raise RuntimeError("Cloud API returned empty content after filtering.")
    return text


def build_user_prompt(
    raw_notes: str, source_type: str, source_id: str, date_str: str
) -> str:
    return f"""Date: {date_str}
Source: {source_type}:{source_id}

Raw notes:
{raw_notes}

Please generate a structured daily report in Markdown.
At the very top, include two single-line fields:
Title: <short, specific title>
Tags: <comma-separated, 2-6 tags>
Add a title line after that: '# Daily Report - {date_str}'.
Use the required section order exactly.
Use bullet lists in each section.
"""


def ensure_minimum_sections(text: str, date_str: str) -> str:
    required = [
        "## What I Did Today",
        "## Problems / Blockers",
        "## Root Cause",
        "## Attempts & Fixes",
        "## Key Learnings",
        "## Metrics",
        "## Next Steps (Tomorrow)",
    ]
    if all(sec in text for sec in required):
        return text

    # fallback: wrap output into standard structure
    return f"""# Daily Report - {date_str}

## What I Did Today
- N/A

## Problems / Blockers
- N/A

## Root Cause
- N/A

## Attempts & Fixes
- N/A

## Key Learnings
- N/A

## Metrics
- N/A

## Next Steps (Tomorrow)
- [ ] N/A

---

### Raw Model Output
{text}
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate structured daily report from rough notes using cloud API."
    )
    parser.add_argument("--input", required=True, help="Path to rough note file")
    parser.add_argument("--output", required=True, help="Output markdown path")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument(
        "--source-type", default="manual", choices=["manual", "commit", "issue"]
    )
    parser.add_argument("--source-id", default="local")
    parser.add_argument(
        "--force", action="store_true", help="Force regeneration even if hash matches"
    )
    args = parser.parse_args()

    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 2

    raw_notes = input_path.read_text(encoding="utf-8")
    input_hash = compute_hash(raw_notes)
    system_prompt = getenv("REPORT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

    user_prompt = build_user_prompt(
        raw_notes, args.source_type, args.source_id, args.date
    )
    out = pathlib.Path(args.output)

    # Idempotency check (prefer hash index)
    if not args.force:
        hash_index = load_report_hash_index(out.parent)
        if input_hash in hash_index:
            print(
                f"No changes detected for: {out} (Hash match in index). Use --force to override."
            )
            return 0
        if out.exists():
            existing = out.read_text(encoding="utf-8")
            meta = parse_frontmatter(existing)
            # Check if the input hash matches the one in the existing file
            if meta.get("input_hash") == input_hash:
                print(
                    f"No changes detected for: {out} (Hash match). Use --force to override."
                )
                return 0

    text = call_cloud_api(user_prompt=user_prompt, system_prompt=system_prompt)

    # Parse the returned text to find the "slug" or "title" to determine filename
    meta = parse_frontmatter(text)
    if not meta:
        meta, text = extract_frontmatter_block(text)

    # 1. Extract Fields
    title = meta.get("title", "")
    slug = meta.get("slug", "")
    if slug:
        slug = slug.strip().strip('"').strip("'")

    tags_str = meta.get(
        "tags", "[]"
    )  # Expecting string like '["a", "b"]' or plain list

    # 2. Normalize Slug
    # If LLM didn't provide slug, try to make one from title
    if not slug and title:
        slug = slugify(title)

    # Fallback to existing logic if still empty
    if not slug:
        # existing extract_title_tags logic as backup
        extracted_title, extracted_tags, cleaned = extract_title_tags(text)
        slug = slugify(extracted_title) if extracted_title else "daily-report"
        title = extracted_title if not title else title
        # merge tags
        if not tags_str or tags_str == "[]":
            tags = extracted_tags
        else:
            # re-parse string tags if needed
            pass

    # 3. Construct Final Path
    # The workflow passes a default --output path (e.g. .../YYYY-MM-DD-issue-123.md)
    # We want to respect the directory but change the filename if we found a better slug.
    out_path = pathlib.Path(args.output)
    out_dir = out_path.parent

    # Only rename if we got a valid meaningful slug from LLM
    # and it's not just the default "daily-report"
    if slug and slug != "daily-report" and slug != "note":
        new_filename = f"{args.date}-{slug}.md"
        final_output_path = out_dir / new_filename
    else:
        final_output_path = out_path

    # Clean the text again just in case
    _, _, cleaned = extract_title_tags(text)
    cleaned = ensure_minimum_sections(cleaned, args.date)

    if not title:
        title = f"Daily Report - {args.date}"

    # --- Validation / Quality Gate ---
    # Parse tags from the meta dict if possible, else rely on extraction
    # We need a list for the frontmatter reconstruction
    final_tags = []
    if isinstance(tags_str, list):
        final_tags = tags_str
    elif isinstance(tags_str, str):
        # basic cleanup of string representation
        t_clean = tags_str.strip("[]").replace('"', "").replace("'", "")
        final_tags = [t.strip() for t in t_clean.split(",") if t.strip()]

    is_standardized = True
    if not final_tags:
        final_tags = ["untagged"]
        is_standardized = False

    frontmatter_lines = [
        "---",
        f"title: {title}",
        f"slug: {slug}",
        f"date: {args.date}",
        f"source_type: {args.source_type}",
        f"source_id: {args.source_id}",
        f"input_hash: {input_hash}",
        f"generated_at: {dt.datetime.now(dt.timezone.utc).isoformat()}",
    ]
    if final_tags:
        tag_str = ", ".join(f'"{t}"' for t in final_tags)
        frontmatter_lines.append(f"tags: [{tag_str}]")

    frontmatter_lines.append("---")

    out_dir.mkdir(parents=True, exist_ok=True)
    final_text = "\n".join(frontmatter_lines) + "\n\n" + cleaned

    final_output_path.write_text(
        final_text + ("\n" if not final_text.endswith("\n") else ""),
        encoding="utf-8",
    )

    # Update hash index for faster idempotency checks
    update_report_hash_index(out_dir, input_hash)

    # IMPORTANT: Print the actual path written so workflows can capture it
    print(f"REPORT_PATH={final_output_path}")
    print(f"Wrote report: {final_output_path}")

    if not is_standardized:
        print(
            "::warning::Generated report missing standard tags/title. Review recommended."
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
