"""Run a deployment smoke test against a MailMind API.

Examples:
    python -m scripts.smoke_deployment --base-url http://localhost:8000/api/v1
    python -m scripts.smoke_deployment --base-url https://api.example.com/api/v1 --cleanup-undo

The script assumes the demo inbox has already been seeded with
`python -m scripts.seed_demo_inbox --count 150 --reset`.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys
from typing import Any, Iterable

import httpx

DEMO_EMAIL = "demo@mailmind.dev"
DEMO_PASSWORD = "DemoPass123!"


@dataclass(frozen=True)
class SmokeCheck:
    name: str
    detail: str


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _get_json(client: httpx.Client, base_url: str, path: str, token: str | None = None) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else None
    response = client.get(_url(base_url, path), headers=headers)
    response.raise_for_status()
    return response.json()


def _post_json(
    client: httpx.Client,
    base_url: str,
    path: str,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else None
    response = client.post(_url(base_url, path), headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def login_demo(client: httpx.Client, base_url: str, email: str, password: str) -> str:
    response = client.post(
        _url(base_url, "/auth/login"),
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    _require(bool(token), "Login response did not include access_token")
    return str(token)


def run_smoke(
    base_url: str,
    email: str = DEMO_EMAIL,
    password: str = DEMO_PASSWORD,
    cleanup_undo: bool = False,
    timeout: float = 20.0,
) -> list[SmokeCheck]:
    checks: list[SmokeCheck] = []
    with httpx.Client(timeout=timeout) as client:
        healthz = _get_json(client, base_url, "/healthz")
        _require(healthz == {"status": "ok"}, f"Unexpected /healthz payload: {healthz}")
        checks.append(SmokeCheck("healthz", "API healthz returned ok"))

        health = _get_json(client, base_url, "/health")
        _require(health == {"status": "ok"}, f"Unexpected /health payload: {health}")
        checks.append(SmokeCheck("health", "API health alias returned ok"))

        token = login_demo(client, base_url, email, password)
        checks.append(SmokeCheck("auth.login", f"Logged in as {email}"))

        me = _get_json(client, base_url, "/auth/me", token)
        _require(me.get("email") == email, f"Unexpected /auth/me email: {me}")
        checks.append(SmokeCheck("auth.me", "JWT protected /me returned demo user"))

        accounts = _get_json(client, base_url, "/gmail/accounts", token)
        _require(len(accounts) >= 1, "No Gmail/demo account found. Seed demo inbox first.")
        checks.append(SmokeCheck("gmail.accounts", f"Found {len(accounts)} Gmail/demo account(s)"))

        emails = _get_json(client, base_url, "/gmail/emails?limit=5", token)
        _require(emails.get("total", 0) > 0, "No emails found. Seed demo inbox first.")
        checks.append(SmokeCheck("gmail.emails", f"Email API returned total={emails['total']}"))

        insights = _get_json(client, base_url, "/gmail/insights", token)
        _require("score" in insights, "Inbox insights response did not include score")
        checks.append(SmokeCheck("gmail.insights", f"Inbox health score={insights['score']}"))

        cleanup = _get_json(client, base_url, "/gmail/cleanup/preview?limit=5", token)
        _require(cleanup.get("total_candidates", 0) > 0, "Cleanup preview returned no candidates")
        checks.append(SmokeCheck("gmail.cleanup.preview", f"Cleanup candidates={cleanup['total_candidates']}"))

        search = _get_json(client, base_url, "/gmail/search?q=electricity%20bill&limit=5", token)
        _require(len(search.get("results", [])) > 0, "Search returned no results")
        checks.append(SmokeCheck("gmail.search", f"Search returned {len(search['results'])} result(s)"))

        sync_health = _get_json(client, base_url, "/gmail/sync/health", token)
        _require("total_jobs" in sync_health, "Sync health response did not include total_jobs")
        checks.append(SmokeCheck("gmail.sync.health", f"Sync jobs={sync_health['total_jobs']}"))

        usage = _get_json(client, base_url, "/gmail/ai/usage", token)
        _require("total_tokens" in usage, "AI usage response did not include total_tokens")
        checks.append(SmokeCheck("gmail.ai.usage", f"AI usage tokens={usage['total_tokens']}"))

        if cleanup_undo:
            email_id = cleanup["items"][0]["email"]["id"]
            action = _post_json(
                client,
                base_url,
                "/gmail/cleanup/actions",
                token,
                {"email_ids": [email_id], "action": "mark_read"},
            )
            _require(action.get("action_ids"), "Cleanup action did not return action_ids")
            undo = _post_json(client, base_url, f"/gmail/cleanup/actions/{action['action_ids'][0]}/undo", token)
            _require(undo.get("action_id") == action["action_ids"][0], "Cleanup undo returned unexpected action_id")
            checks.append(SmokeCheck("gmail.cleanup.undo", f"Applied and undid mark_read for email_id={email_id}"))

    return checks


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1", help="MailMind API base URL ending in /api/v1")
    parser.add_argument("--email", default=DEMO_EMAIL)
    parser.add_argument("--password", default=DEMO_PASSWORD)
    parser.add_argument("--cleanup-undo", action="store_true", help="Also test cleanup action plus undo on one demo email")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        checks = run_smoke(
            base_url=args.base_url,
            email=args.email,
            password=args.password,
            cleanup_undo=args.cleanup_undo,
            timeout=args.timeout,
        )
    except Exception as exc:
        print(f"MailMind deployment smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("MailMind deployment smoke passed")
    for check in checks:
        print(f"  OK {check.name}: {check.detail}")


if __name__ == "__main__":
    main()