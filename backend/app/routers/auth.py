"""Authentication endpoints: register, login, current user.

The login route accepts BOTH JSON and OAuth2 form encoding. The PWA posts JSON; Swagger
UI's "Authorize" button posts a form. Supporting both means /docs can exercise every
protected route interactively, which is worth the small amount of branching.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    AuthError,
    CurrentUser,
    create_access_token,
    hash_password,
    resolve_identifier,
    validate_email,
    validate_password,
    validate_phone,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas import RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> dict:
    token, expires_in = create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": UserOut.model_validate(user),
    }


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    """Create an account and return a token, so the farmer is signed in immediately.

    Requiring a separate login after sign-up is friction with no security benefit.

    A phone number, an email address, or both. The schema guarantees at least one is
    present; each supplied value is format-checked and uniqueness-checked separately, so
    the error names the field that actually clashed.
    """
    validate_password(payload.password)

    phone = validate_phone(payload.phone) if (payload.phone or "").strip() else None
    email = validate_email(payload.email) if (payload.email or "").strip() else None

    # 409 rather than 422: the request is well-formed, the resource just exists.
    if phone and db.scalar(select(User).where(User.phone == phone)):
        raise HTTPException(
            status_code=409,
            detail="An account with this mobile number already exists. Please sign in.",
        )
    if email and db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=409,
            detail="An account with this email address already exists. Please sign in.",
        )

    user = User(
        phone=phone,
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        preferred_language=payload.preferred_language,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    db: Session = Depends(get_db),
    # Populated when Swagger UI posts application/x-www-form-urlencoded.
    username: str | None = Form(default=None),
    password: str | None = Form(default=None),
) -> dict:
    """Sign in with a mobile number OR an email address, plus the password."""
    identifier: str | None = username
    secret: str | None = password

    # JSON path (the PWA). Form fields stay None in that case.
    if identifier is None or secret is None:
        try:
            body = await request.json()
        except Exception:
            body = {}
        # `identifier` is the current field; `phone`/`email` keep older clients working.
        identifier = body.get("identifier") or body.get("phone") or body.get("email")
        secret = body.get("password")

    if not identifier or not secret:
        raise HTTPException(
            status_code=422,
            detail="Enter your mobile number or email address, and your password.",
        )

    user = resolve_identifier(db, identifier)

    # One message for "no such account" and "wrong password" — distinguishing them tells
    # an attacker which numbers and addresses are registered.
    if user is None or not verify_password(secret, user.password_hash):
        raise AuthError("Incorrect mobile number / email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated.")

    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    """The signed-in user. Used by the PWA to validate a stored token on startup."""
    return user
