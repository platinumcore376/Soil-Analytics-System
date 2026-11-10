"""Add users.email and relax the NOT NULL on users.phone.

Sign-in now accepts either identifier, so neither column can be mandatory on its own.
"At least one is present" is enforced in the schema layer, where the error message can name
the actual problem instead of surfacing an IntegrityError.

Idempotent — safe to re-run.

    python scripts/migrate_add_email.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import engine  # noqa: E402


def main() -> int:
    from app import models  # noqa: F401  register models

    print(f"Database: {engine.url.render_as_string(hide_password=True)}")

    columns = {c["name"]: c for c in inspect(engine).get_columns("users")}

    with engine.begin() as conn:
        if "email" in columns:
            print("  users.email: already present")
        else:
            conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255)"))
            # Unique, but NULLs do not collide in Postgres — many users can have no email.
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"
                )
            )
            print("  users.email: added (nullable, unique index)")

        phone = columns.get("phone")
        if phone is not None and not phone["nullable"]:
            conn.execute(text("ALTER TABLE users ALTER COLUMN phone DROP NOT NULL"))
            print("  users.phone: NOT NULL dropped (email-only accounts are now valid)")
        else:
            print("  users.phone: already nullable")

        # Guard against a row with neither identifier, which no code path should create
        # but which would be unreachable — it could never sign in.
        orphans = conn.execute(
            text("SELECT count(*) FROM users WHERE phone IS NULL AND email IS NULL")
        ).scalar_one()
        if orphans:
            print(
                f"\n  WARNING: {orphans} user(s) have neither phone nor email and cannot "
                "sign in. Investigate before relying on this table."
            )
        else:
            print("  every user has at least one identifier")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
