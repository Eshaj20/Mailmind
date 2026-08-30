"""Export a user's already-synced emails to a CSV template for hand-labeling.

This is how you build a real evaluation set: sync your inbox (Week 2/3
features), export it here, then fill in the label_* columns by hand for
100-150 emails before running scripts/evaluate_classifier.py.

Usage (from backend/):
    python -m scripts.export_emails_for_labeling --email you@example.com --limit 150
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.gmail import Email  # noqa: E402
from app.models.user import User  # noqa: E402

# Main function to parse command-line arguments, query the database for the specified user's synced emails, and export them to a CSV file with empty label columns for hand-labeling.
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="The MailMind account email to export emails for")
    parser.add_argument("--output", default="eval/private/labeled_emails_real.csv", help="Where to write the private CSV template")
    parser.add_argument("--limit", type=int, default=150, help="Max emails to export (aim for 100-150)")
    args = parser.parse_args()

# Connect to the database and query for the specified user and their synced emails, then write the results to a CSV file with empty label columns for hand-labeling.
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == args.email))
        if user is None:
            raise SystemExit(f"No MailMind user found for {args.email}")

        emails = list(
            db.scalars(
                select(Email)
                .where(Email.user_id == user.id)
                .order_by(Email.received_at.desc())
                .limit(args.limit)
            )
        )
        # If no synced emails are found for the user, exit the script with an error message indicating that a Gmail sync should be run first.
        if not emails:
            raise SystemExit("No synced emails found. Run a Gmail sync first (Week 2/3 features).")

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the emails to a CSV file with the specified columns, leaving the label columns empty for hand-labeling.
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "gmail_message_id",
                    "sender",
                    "subject",
                    "snippet",
                    "body_preview",
                    "label_category",
                    "label_priority",
                    "label_needs_reply",
                ]
            )
            for email in emails:
                writer.writerow(
                    [
                        email.gmail_message_id,
                        email.sender or "",
                        email.subject or "",
                        email.snippet or "",
                        email.body_preview or "",
                        "",
                        "",
                        "",
                    ]
                )

        print(f"Wrote {len(emails)} rows to {output_path}.")
        print("Keep this file private; it contains real email metadata/snippets and is ignored by Git.")
        print("Fill in the label_* columns by hand:")
        print("  label_category: primary | promotions | social | updates | spam")
        print("  label_priority: high | medium | low")
        print("  label_needs_reply: true | false")
    finally:
        db.close()


if __name__ == "__main__":
    main()
