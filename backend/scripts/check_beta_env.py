"""Validate MailMind's private no-card beta configuration without printing secrets.

Run from the repository root:
    .\.venv\Scripts\python.exe backend\scripts\check_beta_env.py

Add --require-oauth once Google OAuth credentials are available.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


REQUIRED_KEYS = (
    "DATABASE_URL",
    "SECRET_KEY",
    "CORS_ORIGINS",
    "FRONTEND_APP_URL",
)
OAUTH_KEYS = (
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REDIRECT_URI",
)
PLACEHOLDER_MARKERS = (
    "replace-",
    "your-",
    "postgresql://user:",
    "https://replace-",
    "project_ref",
    "password",
    "pooler_host",
)


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def is_configured(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.lower()
    return not any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.beta"))
    parser.add_argument("--require-oauth", action="store_true")
    args = parser.parse_args()

    if not args.env_file.exists():
        print(f"Missing {args.env_file}. Copy .env.beta.example first.", file=sys.stderr)
        raise SystemExit(1)

    values = read_env_file(args.env_file)
    required = REQUIRED_KEYS + (OAUTH_KEYS if args.require_oauth else ())
    missing = [key for key in required if not is_configured(values.get(key))]

    for key in REQUIRED_KEYS + OAUTH_KEYS:
        state = "configured" if is_configured(values.get(key)) else "missing or placeholder"
        print(f"{key}: {state}", flush=True)

    if values.get("DATABASE_URL", "").startswith("postgresql://") and ":5432/" not in values["DATABASE_URL"]:
        print("DATABASE_URL note: use the Supabase Session pooler URL on port 5432 for this long-running API/worker beta.")

    if missing:
        print("\nPreflight failed. Fill the missing values without committing .env.beta.")
        raise SystemExit(1)

    print("\nBeta environment preflight passed.")


if __name__ == "__main__":
    main()
