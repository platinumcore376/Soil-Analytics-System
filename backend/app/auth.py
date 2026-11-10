"""Authentication: password hashing, JWT issue/verify, and request dependencies.

DESIGN
------
* **Phone OR email as the identity.** A mobile number is near-universal among the
  smallholder farmers this targets; email suits extension officers and desktop users.
  Sign-in accepts either — `resolve_identifier` decides which column to match on by
  looking for an "@", so the farmer never has to pick a field type.

* **bcrypt for passwords.** Deliberately slow, per-hash salt, and the cost factor can be
  raised later without invalidating existing hashes. `passlib` is not used — it is
  unmaintained and warns on modern bcrypt; the `bcrypt` package alone is enough.

* **Stateless JWT.** No server-side session store, so the API stays horizontally
  scalable. The trade-off is that a token cannot be revoked before it expires; tokens are
  therefore short-lived and `is_active` is re-checked from the database on every request,
  which gives a way to lock an account out immediately.

* **`JWT_SECRET` has no default.** A hardcoded fallback secret is the classic way a
  development shortcut reaches production and forges tokens for everyone. The app refuses
  to start without one.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Farm, Field as FieldModel, User

ALGORITHM = "HS256"

# tokenUrl drives the Swagger "Authorize" button, so /docs can exercise protected routes.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

# Indian mobile numbers: 10 digits starting 6-9, optionally +91-prefixed. Kept permissive
# on separators because farmers type numbers inconsistently.
PHONE_PATTERN = re.compile(r"^(?:\+?91)?[6-9]\d{9}$")

# Deliberately permissive: something@something.tld. Stricter regexes reject valid
# addresses, and the only real proof of an email is sending to it.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

MIN_PASSWORD_LENGTH = 8

# bcrypt truncates silently at 72 bytes; rejecting longer input is clearer than having
# two different long passwords authenticate each other.
MAX_PASSWORD_BYTES = 72


class AuthError(HTTPException):
    """401 with the WWW-Authenticate header clients need to prompt for credentials."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def normalise_phone(phone: str) -> str:
    """Strip separators and the country code so one number has one stored form.

    Without this, '+91 98765 43210' and '9876543210' would be two different accounts.
    """
    digits = re.sub(r"[\s\-()]", "", phone.strip())
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits


def validate_phone(phone: str) -> str:
    normalised = normalise_phone(phone)
    if not PHONE_PATTERN.match(normalised):
        raise HTTPException(
            status_code=422,
            detail=(
                "Enter a valid 10-digit Indian mobile number starting with 6, 7, 8 or 9."
            ),
        )
    return normalised


def normalise_email(email: str) -> str:
    """Lower-case and trim, so Ramesh@Farm.com and ramesh@farm.com are one account."""
    return email.strip().lower()


def validate_email(email: str) -> str:
    normalised = normalise_email(email)
    if not EMAIL_PATTERN.match(normalised):
        raise HTTPException(
            status_code=422, detail="Enter a valid email address, e.g. name@example.com."
        )
    return normalised


def looks_like_email(identifier: str) -> bool:
    """An '@' is the only thing that distinguishes the two identifier forms."""
    return "@" in identifier


def resolve_identifier(db: Session, identifier: str) -> User | None:
    """Find a user by phone or email, whichever the string looks like.

    Doing this by shape rather than asking the caller which field they typed keeps the
    sign-in form to a single input — one less decision for the farmer.
    """
    value = identifier.strip()
    if not value:
        return None
    if looks_like_email(value):
        return db.scalar(select(User).where(User.email == normalise_email(value)))
    return db.scalar(select(User).where(User.phone == normalise_phone(value)))


def validate_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Password must be at most {MAX_PASSWORD_BYTES} bytes. bcrypt ignores "
                "anything beyond that, which would make two different passwords "
                "interchangeable."
            ),
        )
    return password


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed stored hash — treat as a failed login, never as a pass.
        return False


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
def create_access_token(user_id: int) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    expires_in = settings.jwt_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),  # JWT spec requires `sub` to be a string
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, expires_in


def decode_token(token: str) -> int:
    """Return the user id from a valid token, else raise 401."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthError("Your session has expired. Please sign in again.") from None
    except jwt.InvalidTokenError:
        raise AuthError("Invalid authentication token.") from None

    subject = payload.get("sub")
    if subject is None:
        raise AuthError("Invalid authentication token.")
    try:
        return int(subject)
    except (TypeError, ValueError):
        raise AuthError("Invalid authentication token.") from None


# --------------------------------------------------------------------------- #
# Request dependencies
# --------------------------------------------------------------------------- #
def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the authenticated user, or raise 401.

    The user is re-read from the database on every request rather than trusted from the
    token payload. That costs one indexed lookup and buys immediate deactivation — a
    stateless JWT otherwise stays valid until it expires.
    """
    if not token:
        raise AuthError("Not authenticated.")

    user_id = decode_token(token)
    user = db.get(User, user_id)
    if user is None:
        raise AuthError("Account no longer exists.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def owned_farm(db: Session, farm_id: int, user: User) -> Farm:
    """Fetch a farm the user owns, else raise.

    404 rather than 403 for someone else's farm: a 403 would confirm the id exists,
    letting an attacker enumerate other users' data.
    """
    farm = db.get(Farm, farm_id)
    if farm is None or farm.user_id != user.id:
        raise HTTPException(status_code=404, detail=f"Farm {farm_id} not found.")
    return farm


def owned_farm_ids(db: Session, user: User) -> list[int]:
    """All farm ids belonging to the user — the basis of every ownership filter."""
    return list(db.scalars(select(Farm.id).where(Farm.user_id == user.id)))


def owned_field(db: Session, field_id: int, user: User) -> FieldModel:
    """Fetch a field whose farm the user owns, else 404.

    Fields, records, images and analyses all inherit ownership through their farm — this
    is the single join every guard funnels through, so there is one place to audit.
    """
    field = db.get(FieldModel, field_id)
    if field is None:
        raise HTTPException(status_code=404, detail=f"Field {field_id} not found.")

    farm = db.get(Farm, field.farm_id)
    if farm is None or farm.user_id != user.id:
        # Same 404 as a non-existent field: a 403 here would confirm the id is real.
        raise HTTPException(status_code=404, detail=f"Field {field_id} not found.")
    return field


def owns_field(db: Session, field_id: int | None, user: User) -> bool:
    """Non-raising ownership test, for optional foreign keys."""
    if field_id is None:
        return False
    try:
        owned_field(db, field_id, user)
        return True
    except HTTPException:
        return False

