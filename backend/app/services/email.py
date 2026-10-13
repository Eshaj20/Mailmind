import smtplib
from email.message import EmailMessage

from app.core.config import settings


class EmailDeliveryError(Exception):
    pass


def password_reset_delivery_is_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email)


def send_password_reset_email(recipient: str, reset_link: str) -> None:
    """Send a single-use password-reset link through the configured SMTP provider."""
    if not password_reset_delivery_is_configured():
        raise EmailDeliveryError("Password reset email is not configured")

    message = EmailMessage()
    message["Subject"] = "Reset your MailMind password"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        "We received a request to reset your MailMind password.\n\n"
        f"Open this link within {settings.password_reset_token_expire_minutes} minutes:\n{reset_link}\n\n"
        "If you did not request this, you can safely ignore this email."
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_starttls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Unable to send password reset email") from exc
