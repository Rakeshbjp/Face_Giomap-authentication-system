# pyre-ignore-all-errors
"""
Email notification service for authentication events.

Sends styled email alerts on:
- Registration success / failure
- Login success / failure
- Location mismatch
- Logout

Uses Gmail SMTP with App Passwords.
All templates include user details + address information for consistency.
"""

import logging
import os
from datetime import datetime

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
#  Shared HTML snippets
# ──────────────────────────────────────────────

_USER_DETAILS_BLOCK = """
            <div style="margin: 20px 0; padding: 15px; background: {bg}; border-radius: 8px; border: 1px solid {border};">
                <p style="margin: 0 0 6px 0; color: {label_color}; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Account Details</p>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px; color: {text_color};">
                    <tr><td style="padding: 4px 0; font-weight: 600; width: 80px;">Name</td><td style="padding: 4px 0;">{user_name}</td></tr>
                    <tr><td style="padding: 4px 0; font-weight: 600;">Email</td><td style="padding: 4px 0;">{user_email}</td></tr>
                    <tr><td style="padding: 4px 0; font-weight: 600;">Phone</td><td style="padding: 4px 0;">{user_phone}</td></tr>
                </table>
            </div>
"""

_ADDRESS_BLOCK = """
            <div style="margin: 15px 0; padding: 15px; background: {bg}; border-radius: 8px; border: 1px solid {border};">
                <p style="margin: 0 0 6px 0; color: {label_color}; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">📍 {label}</p>
                <p style="margin: 0; color: {text_color}; font-size: 14px; line-height: 1.5;">{address_line}</p>
            </div>
"""

_TIMESTAMP_LINE = """
            <p style="color: #9ca3af; font-size: 12px; margin: 15px 0 0 0;">
                🕐 Time: <strong>{timestamp}</strong>
            </p>
"""


# ──────────────────────────────────────────────
#  Email Templates
# ──────────────────────────────────────────────

_TEMPLATES = {
    ("register", "success"): (
        "✅ Registration Successful — Face Auth",
        """
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 540px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #f0fdf4; border: 1px solid #bbf7d0;">
            <h2 style="color: #166534; margin-top: 0;">✅ Registration Successful!</h2>
            <p style="color: #14532d; font-size: 15px; line-height: 1.6;">
                Welcome! Your account has been successfully created on <b>Face Auth</b>.<br>
                You can now log in using your credentials.
            </p>
            """
            + _USER_DETAILS_BLOCK.replace("{bg}", "#dcfce7").replace("{border}", "#bbf7d0").replace("{label_color}", "#166534").replace("{text_color}", "#14532d")
            + _ADDRESS_BLOCK.replace("{bg}", "#dcfce7").replace("{border}", "#bbf7d0").replace("{label_color}", "#166534").replace("{text_color}", "#14532d").replace("{label}", "Registered Location")
            .replace("{address_line}", "{address_display}")
            + _TIMESTAMP_LINE
            + """
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
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 540px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #fef2f2; border: 1px solid #fecaca;">
            <h2 style="color: #991b1b; margin-top: 0;">❌ Registration Failed</h2>
            <p style="color: #7f1d1d; font-size: 15px; line-height: 1.6;">
                An attempt to register with your email on <b>Face Auth</b> was unsuccessful.<br>
                This may be because the email is already registered.
            </p>
            """
            + _ADDRESS_BLOCK.replace("{bg}", "#fee2e2").replace("{border}", "#fecaca").replace("{label_color}", "#991b1b").replace("{text_color}", "#7f1d1d").replace("{label}", "Attempt Location")
            .replace("{address_line}", "{address_display}")
            + _TIMESTAMP_LINE
            + """
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
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 540px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #f0fdf4; border: 1px solid #bbf7d0;">
            <h2 style="color: #166534; margin-top: 0;">✅ Login Successful!</h2>
            <p style="color: #14532d; font-size: 15px; line-height: 1.6;">
                You have successfully logged into your <b>Face Auth</b> account.
            </p>
            """
            + _USER_DETAILS_BLOCK.replace("{bg}", "#dcfce7").replace("{border}", "#bbf7d0").replace("{label_color}", "#166534").replace("{text_color}", "#14532d")
            + _ADDRESS_BLOCK.replace("{bg}", "#dcfce7").replace("{border}", "#bbf7d0").replace("{label_color}", "#166534").replace("{text_color}", "#14532d").replace("{label}", "Login Location")
            .replace("{address_line}", "{address_display}")
            + _TIMESTAMP_LINE
            + """
            <hr style="border: none; border-top: 1px solid #bbf7d0; margin: 20px 0;">
            <p style="color: #6b7280; font-size: 12px;">
                If this wasn't you, please reset your password immediately.<br>
                This is an automated security notification.
            </p>
        </div>
        """,
    ),
    ("login", "failure"): (
        "❌ Login Failed — Face Auth",
        """
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 540px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #fef2f2; border: 1px solid #fecaca;">
            <h2 style="color: #991b1b; margin-top: 0;">❌ Login Attempt Failed</h2>
            <p style="color: #7f1d1d; font-size: 15px; line-height: 1.6;">
                A failed login attempt was detected on your <b>Face Auth</b> account.
            </p>
            """
            + _ADDRESS_BLOCK.replace("{bg}", "#fee2e2").replace("{border}", "#fecaca").replace("{label_color}", "#991b1b").replace("{text_color}", "#7f1d1d").replace("{label}", "Attempt Location")
            .replace("{address_line}", "{address_display}")
            + _TIMESTAMP_LINE
            + """
            <hr style="border: none; border-top: 1px solid #fecaca; margin: 20px 0;">
            <p style="color: #6b7280; font-size: 12px;">
                If this wasn't you, please secure your account immediately.<br>
                This is an automated security notification.
            </p>
        </div>
        """,
    ),
    ("login", "location_mismatch"): (
        "📍 Location Mismatch Detected — Face Auth",
        """
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 540px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #fffbeb; border: 1px solid #fde68a;">
            <h2 style="color: #b45309; margin-top: 0;">📍 Location Mismatch</h2>
            <p style="color: #92400e; font-size: 15px; line-height: 1.6;">
                A login attempt was blocked due to a location mismatch on your <b>Face Auth</b> account.<br><br>
                <strong>Location mismatch detected!</strong> You can only login from your registered location.
                To log in from this new location, you must register a new account first.
            </p>
            """
            + _USER_DETAILS_BLOCK.replace("{bg}", "white").replace("{border}", "#fde68a").replace("{label_color}", "#b45309").replace("{text_color}", "#92400e")
            + """
            <div style="margin: 20px 0; padding: 15px; background: white; border-radius: 8px; border: 1px solid #fde68a;">
                <p style="margin: 0 0 10px 0; color: #b45309;"><strong>📍 Registered Location:</strong><br/>
                <span style="color: #92400e;">{reg_display}</span></p>
                
                <p style="margin: 0; color: #b45309;"><strong>⚠️ Current Attempt Location:</strong><br/>
                <span style="color: #92400e;">{curr_display}</span></p>
            </div>
            """
            + _TIMESTAMP_LINE
            + """
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
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 540px; margin: auto;
                    padding: 32px; border-radius: 12px; background: #f3f4f6; border: 1px solid #d1d5db;">
            <h2 style="color: #374151; margin-top: 0;">👋 Secure Session Ended</h2>
            <p style="color: #4b5563; font-size: 15px; line-height: 1.6;">
                You have successfully logged out of your <b>Face Auth</b> account.<br>
                Your session has been terminated securely.
            </p>
            """
            + _USER_DETAILS_BLOCK.replace("{bg}", "#e5e7eb").replace("{border}", "#d1d5db").replace("{label_color}", "#374151").replace("{text_color}", "#4b5563")
            + _TIMESTAMP_LINE
            + """
            <hr style="border: none; border-top: 1px solid #d1d5db; margin: 20px 0;">
            <p style="color: #6b7280; font-size: 12px;">
                This is an automated notification.
            </p>
        </div>
        """,
    ),
}


# ──────────────────────────────────────────────
#  Helper: Format address dict to string
# ──────────────────────────────────────────────

def format_address_for_email(addr: dict | None, lat: float = None, lng: float = None) -> str:
    """
    Convert an address dict (from reverse_geocode) to a single-line
    human-readable string for email templates.
    """
    if not addr:
        if lat is not None and lng is not None:
            return f"{lat:.6f}, {lng:.6f}"
        return "Location not available"

    if "fallback" in addr:
        return addr["fallback"]

    parts = [
        addr.get("road"),
        addr.get("area") or addr.get("suburb"),
        addr.get("city"),
        addr.get("state"),
        addr.get("country"),
        addr.get("pincode"),
    ]
    valid = [p for p in parts if p and str(p).strip()]
    if valid:
        return ", ".join(valid)

    return addr.get("display_name") or (f"{lat:.6f}, {lng:.6f}" if lat is not None else "Location not available")


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
        kwargs:   Optional template variables:
            - user_name, user_email, user_phone: user details
            - address_display: formatted address string
            - reg_display, curr_display: for location mismatch
            - timestamp: event time string

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

    # Inject defaults for any missing template variables
    import collections
    defaults = {
        "user_name": "N/A",
        "user_email": to_email,
        "user_phone": "N/A",
        "address_display": "Location not available",
        "reg_display": "",
        "curr_display": "",
        "timestamp": datetime.utcnow().strftime("%d %b %Y, %I:%M %p UTC"),
    }
    defaults.update(kwargs)
    body = raw_body.format_map(collections.defaultdict(str, defaults))

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
