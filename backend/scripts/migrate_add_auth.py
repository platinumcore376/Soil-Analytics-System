"""Add the users table and farms.user_id to an existing database.

`Base.metadata.create_all()` creates missing TABLES but never alters an existing one, so
adding `farms.user_id` needs an explicit migration. This script is idempotent — safe to
re-run — and does not touch existing rows beyond adding the nullable column.

    python scripts/migrate_add_auth.py

WHAT HAPPENS TO PRE-AUTH FARMS
------------------------------
Existing farms keep `user_id = NULL`. They are then invisible to every user, because reads
filter on `user_id == current_user.id`. That is deliberate: silently assigning orphaned
records to the first account to register would hand one farmer another's data.

Pass --assign-to <phone> to claim them for a specific account, e.g. when the existing rows
are your own test data.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/migrate_add_auth.py` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import Base, engine  # noqa: E402


def column_exists(table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(engine).get_columns(table)}


def table_exists(table: str) -> bool:
    return inspect(engine).has_table(table)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--assign-to",
        metavar="PHONE",
        help="Assign existing owner-less farms to this user's phone number.",
    )
    args = parser.parse_args()

    from app import models  # noqa: F401  register models on Base

    print(f"Database: {engine.url.render_as_string(hide_password=True)}")

    # 1. Create any missing tables (users).
    created_users = not table_exists("users")
    Base.metadata.create_all(bind=engine)
    print(f"  users table: {'created' if created_users else 'already present'}")

    # 2. Add farms.user_id if absent.
    with engine.begin() as conn:
        if column_exists("farms", "user_id"):
            print("  farms.user_id: already present")
        else:
            conn.execute(text("ALTER TABLE farms ADD COLUMN user_id INTEGER"))
            conn.execute(
                text(
                    "ALTER TABLE farms ADD CONSTRAINT farms_user_id_fkey "
                    "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_farms_user_id ON farms (user_id)")
            )
            print("  farms.user_id: added (nullable, FK -> users.id, indexed)")

    # 3. Report or fix orphans.
    with engine.begin() as conn:
        orphans = conn.execute(
            text("SELECT count(*) FROM farms WHERE user_id IS NULL")
        ).scalar_one()

        if orphans == 0:
            print("  orphaned farms: none")
            return 0

        if not args.assign_to:
            print(
                f"\n  {orphans} farm(s) have no owner and are therefore invisible to all "
                "users.\n  Re-run with --assign-to <phone> to claim them for an account."
            )
            return 0

        user_id = conn.execute(
            text("SELECT id FROM users WHERE phone = :phone"), {"phone": args.assign_to}
        ).scalar()
        if user_id is None:
            print(
                f"\n  No user with phone {args.assign_to!r}. Register that account first, "
                "then re-run."
            )
            return 1

        conn.execute(
            text("UPDATE farms SET user_id = :uid WHERE user_id IS NULL"),
            {"uid": user_id},
        )
        print(f"  assigned {orphans} orphaned farm(s) to user {user_id} ({args.assign_to})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
