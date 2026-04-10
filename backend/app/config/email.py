# pyre-ignore-all-errors
"""
Email notification service for authentication events.

Sends styled email alerts on:
- Registration success / failure
- Login success / failure

Uses Gmail SMTP with App Passwords.
"""

import logging
import os

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType  # type: ignore
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  SMTP Connection Configuration
# ──────────────────────────────────────────────

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
    MAIL_FROM=os.getenv("MAIL_FROM", ""),
    MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
)

# Determine whether email sending is configured
_email_enabled = bool(os.getenv("MAIL_USERNAME")) and bool(os.getenv("MAIL_PASSWORD"))

# ──────────────────────────────────────────────
#  Email Templates
# ──────────────────────────────────────────────

_TEMPLATES = {
    ("register", "success"): (
        "✅ Registration Successful — Face Auth",
        """
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #f0fdf4; border: 1px solid #bbf7d0;">
            <h2 style="color: #166534; margin-top: 0;">✅ Registration Successful!</h2>
            <p style="color: #14532d; font-size: 15px; line-height: 1.6;">
                Welcome! Your account has been successfully created on <b>Face Auth</b>.<br>
                You can now log in using your credentials.
            </p>
            <hr style="border: none; border-top: 1px solid #bbf7d0; margin: 20px 0;">
            <p style="color: #6b7280; font-size: 12px;">
                If you did not register for this account, please ignore this email.
            </p>
        </div>
        """,
    ),
    ("register", "failure"): (
        "❌ Registration Failed — Face Auth",
        """
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #fef2f2; border: 1px solid #fecaca;">
            <h2 style="color: #991b1b; margin-top: 0;">❌ Registration Failed</h2>
            <p style="color: #7f1d1d; font-size: 15px; line-height: 1.6;">
                An attempt to register with your email on <b>Face Auth</b> was unsuccessful.<br>
                This may be because the email is already registered. Please check your details and try again.
            </p>
            <hr style="border: none; border-top: 1px solid #fecaca; margin: 20px 0;">
            <p style="color: #6b7280; font-size: 12px;">
                If this wasn't you, you can safely ignore this email.
            </p>
        </div>
        """,
    ),
    ("login", "success"): (
        "✅ Login Successful — Face Auth",
        """
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #f0fdf4; border: 1px solid #bbf7d0;">
            <h2 style="color: #166534; margin-top: 0;">✅ Login Successful!</h2>
            <p style="color: #14532d; font-size: 15px; line-height: 1.6;">
                You have successfully logged into your <b>Face Auth</b> account.<br>
                If this wasn't you, please reset your password immediately.
            </p>
            <hr style="border: none; border-top: 1px solid #bbf7d0; margin: 20px 0;">
            <p style="color: #6b7280; font-size: 12px;">
                This is an automated security notification.
            </p>
        </div>
        """,
    ),
    ("login", "failure"): (
        "❌ Login Failed — Face Auth",
        """
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #fef2f2; border: 1px solid #fecaca;">
            <h2 style="color: #991b1b; margin-top: 0;">❌ Login Attempt Failed</h2>
            <p style="color: #7f1d1d; font-size: 15px; line-height: 1.6;">
                A failed login attempt was detected on your <b>Face Auth</b> account.<br>
                If this wasn't you, please secure your account immediately.
            </p>
            <hr style="border: none; border-top: 1px solid #fecaca; margin: 20px 0;">
            <p style="color: #6b7280; font-size: 12px;">
                This is an automated security notification.
            </p>
        </div>
        """,
    ),
    ("login", "location_mismatch"): (
        "📍 Location Mismatch Detected — Face Auth",
        """
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #fffbeb; border: 1px solid #fde68a;">
            <h2 style="color: #b45309; margin-top: 0;">📍 Location Mismatch</h2>
            <p style="color: #92400e; font-size: 15px; line-height: 1.6;">
                A login attempt was dynamically blocked due to a location mismatch on your <b>Face Auth</b> account.<br><br>
                <strong>Location mismatch detected!</strong> You can only login from your currently registered location.
                To log in from this new location, you must register a new account on this device first.
            </p>
            
            <div style="margin: 20px 0; padding: 15px; background: white; border-radius: 8px; border: 1px solid #fde68a;">
                <p style="margin: 0 0 10px 0; color: #b45309;"><strong>📍 Registered Location:</strong><br/>
                <span style="color: #92400e;">{reg_display}</span></p>
                
                <p style="margin: 0; color: #b45309;"><strong>⚠️ Current Attempt Location:</strong><br/>
                <span style="color: #92400e;">{curr_display}</span></p>
            </div>
            
            <hr style="border: none; border-top: 1px solid #fde68a; margin: 20px 0;">
            <p style="color: #6b7280; font-size: 12px;">
                This is an automated security alert.
            </p>
        </div>
        """,
    ),
    ("login", "logout"): (
        "👋 Logged Out Successfully — Face Auth",
        """
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #f3f4f6; border: 1px solid #d1d5db;">
            <h2 style="color: #374151; margin-top: 0;">👋 Secure Session Ended</h2>
            <p style="color: #4b5563; font-size: 15px; line-height: 1.6;">
                You have successfully securely logged out of your <b>Face Auth</b> account.<br>
                Your session has been terminated successfully.
            </p>
            <hr style="border: none; border-top: 1px solid #d1d5db; margin: 20px 0;">
            <p style="color: #6b7280; font-size: 12px;">
                This is an automated notification.
            </p>
        </div>
        """,
    ),
}


# ──────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────

async def send_auth_email(to_email: str, action: str, status: str, **kwargs) -> None:
    """
    Send an authentication notification email.

    Args:
        to_email: Recipient email address.
        action:   'register' | 'login'
        status:   'success'  | 'failure' | 'location_mismatch' | 'logout'
        kwargs:   Optional template variables (e.g., reg_display, curr_display)

    This function is fire-and-forget — it never raises.
    If email sending is not configured or fails, it logs a warning and returns silently.
    """
    if not _email_enabled:
        logger.debug("Email sending skipped (MAIL_USERNAME / MAIL_PASSWORD not configured)")
        return

    subject, raw_body = _TEMPLATES.get(
        (action, status),
        ("Account Notification — Face Auth", "<p>Account activity detected on your Face Auth account.</p>"),
    )

    import collections
    # Format the body with optional kwargs, defaulting to empty string if missing
    body = raw_body.format_map(collections.defaultdict(str, kwargs))

    try:
        message = MessageSchema(
            subject=subject,
            recipients=[to_email],
            body=body,
            subtype=MessageType.html,
        )
        fm = FastMail(conf)
        await fm.send_message(message)
        logger.info(f"Auth email sent: action={action}, status={status}, to={to_email}")
    except Exception as e:
        logger.warning(f"Failed to send auth email to {to_email}: {e}")
