from datetime import UTC, datetime, timedelta
from hashlib import sha256
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.gmail import Email, EmailThread, GmailAccount
from app.models.user import PasswordResetToken, User
from app.schemas.auth import Message, PasswordResetConfirm, PasswordResetRequest, Token, UserCreate, UserRead
from app.services.email import (
    EmailDeliveryError,
    password_reset_delivery_is_configured,
    send_password_reset_email,
)
from app.services.gmail import redact_sensitive_preview

router = APIRouter()

# Signup endpoint
@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    allowed_emails = settings.beta_allowed_email_set
    if allowed_emails and payload.email.lower() not in allowed_emails:
        raise HTTPException(status_code=403, detail="This beta is currently invite-only")

    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email is already registered")

# Create a new user with hashed password and store it in the database
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# Login endpoint
@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    user = db.scalar(select(User).where(User.email == form_data.username))
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return Token(access_token=create_access_token(subject=str(user.id)))

# Get current user endpoint
@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def _hash_reset_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _scrub_stored_reset_links(db: Session, user_id: int) -> None:
    """Remove reset links already imported before preview redaction existed."""
    account_ids = select(GmailAccount.id).where(GmailAccount.user_id == user_id)
    emails = list(
        db.scalars(
            select(Email).where(
                Email.user_id == user_id,
                (Email.snippet.contains("/#/reset-password?token="))
                | (Email.body_preview.contains("/#/reset-password?token="))
                | (Email.search_text.contains("/#/reset-password?token=")),
            )
        )
    )
    for email in emails:
        email.snippet = redact_sensitive_preview(email.snippet)
        email.body_preview = redact_sensitive_preview(email.body_preview)
        email.search_text = redact_sensitive_preview(email.search_text)

    threads = list(
        db.scalars(
            select(EmailThread).where(
                EmailThread.gmail_account_id.in_(account_ids),
                (EmailThread.snippet.contains("/#/reset-password?token="))
                | (EmailThread.summary.contains("/#/reset-password?token=")),
            )
        )
    )
    for thread in threads:
        thread.snippet = redact_sensitive_preview(thread.snippet)
        thread.summary = redact_sensitive_preview(thread.summary)


@router.post("/password-reset/request", response_model=Message)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> Message:
    """Issue a one-time token without exposing whether the email is registered."""
    if not password_reset_delivery_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email delivery is unavailable. Please try again later.",
        )

    user = db.scalar(select(User).where(User.email == str(payload.email)))
    if user is not None:
        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )
        _scrub_stored_reset_links(db, user.id)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_reset_token(raw_token),
            expires_at=now + timedelta(minutes=settings.password_reset_token_expire_minutes),
        )
        db.add(reset_token)
        db.commit()
        reset_link = (
            f"{settings.frontend_app_url.rstrip('/')}/#/reset-password?token={quote(raw_token)}"
        )
        try:
            send_password_reset_email(user.email, reset_link)
        except EmailDeliveryError:
            # Delivery failures should be monitored in deployment logs, not exposed as account existence.
            return Message(detail="If an account exists for that email, a reset link has been sent.")

    return Message(detail="If an account exists for that email, a reset link has been sent.")


@router.post("/password-reset/confirm", response_model=Message)
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)) -> Message:
    reset_token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_reset_token(payload.token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.now(UTC),
        )
    )
    if reset_token is None:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired")

    user = db.get(User, reset_token.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired")

    user.hashed_password = hash_password(payload.password)
    reset_token.used_at = datetime.now(UTC)
    db.commit()
    return Message(detail="Password updated. You can now log in.")
