import os
import json
import pathlib
import sys

# Define base directory (repo root)
REPO_ROOT = pathlib.Path(__file__).parent.parent.resolve()
ENV_FILE = REPO_ROOT / ".env.secrets"

# Known configuration keys for documentation/GUI hints
KNOWN_KEYS = {
    "OPENAI_API_KEY": "Required for report generation",
    "REPORT_API_URL": "API Endpoint (default: OpenAI)",
    "REPORT_API_MODEL": "Model Name (e.g. gpt-4)",
    "REPORT_SYSTEM_PROMPT": "Custom system prompt override",
}


def load_env() -> dict:
    """
    Loads environment variables from .env.secrets file.
    Returns a dict of key-value pairs found in the file.
    Does NOT modify os.environ directly to avoid pollution,
    but intended to be used as an overlay.
    """
    if not ENV_FILE.exists():
        return {}

    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {ENV_FILE}: {e}", file=sys.stderr)
        return {}


def get_env(key: str, default: str = None) -> str:
    """
    Priority:
    1. Local .env.secrets file
    2. System environment variable (os.environ)
    3. Default value
    """
    local_env = load_env()
    if key in local_env:
        return local_env[key]

    return os.environ.get(key, default)


def save_env(key: str, value: str):
    """Saves a key-value pair to .env.secrets"""
    current = load_env()
    current[key] = value

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    print(f"Saved {key} to {ENV_FILE}")


def list_all_env() -> dict:
    """
    Returns a merged dictionary of all relevant environment variables.
    Merges system env with local secrets.
    """
    # Start with system env, filtered by known keys + anything starting with REPORT_
    merged = {}

    # 1. System Env (Filtered)
    for k, v in os.environ.items():
        if k in KNOWN_KEYS or k.startswith("REPORT_"):
            merged[k] = v

    # 2. Local Secrets (Override)
    local = load_env()
    merged.update(local)

    # 3. Ensure known keys exist (even if empty)
    for k in KNOWN_KEYS:
        if k not in merged:
            merged[k] = ""

    return merged


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage local environment secrets")
    subparsers = parser.add_subparsers(dest="command")

    # list command
    list_parser = subparsers.add_parser("list", help="List all configured variables")

    # set command
    set_parser = subparsers.add_parser("set", help="Set a variable")
    set_parser.add_argument("key", help="Variable name (e.g. OPENAI_API_KEY)")
    set_parser.add_argument("value", help="Value")

    # get command
    get_parser = subparsers.add_parser("get", help="Get a variable value")
    get_parser.add_argument("key", help="Variable name")

    args = parser.parse_args()

    if args.command == "list":
        envs = list_all_env()
        for k, v in envs.items():
            print(f"{k}={v}")

    elif args.command == "set":
        save_env(args.key, args.value)

    elif args.command == "get":
        print(get_env(args.key, ""))

    else:
        parser.print_help()
