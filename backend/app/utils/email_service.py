# pyre-ignore-all-errors
"""
Email notification service using Resend API.
Sends real-time email alerts for registration, login, and failure events.
"""

import logging
import resend
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# IST timezone offset
IST = timezone(timedelta(hours=5, minutes=30))


def _get_ist_time() -> str:
    """Get current time in IST as a formatted string."""
    now = datetime.now(IST)
    return now.strftime("%d %b %Y, %I:%M:%S %p IST")


def _build_address_text(address: dict | None) -> str:
    """Build a clean address string from a geocoded address dict."""
    if not address:
        return "Location not available"
    parts = [
        address.get("road"),
        address.get("area"),
        address.get("suburb"),
        address.get("city"),
        address.get("state"),
        address.get("country"),
    ]
    text = ", ".join(filter(None, parts))
    pincode = address.get("pincode")
    if pincode:
        text += f" - {pincode}"
    return text or address.get("display_name", "Location not available")


def _email_template(
    title: str,
    status_color: str,
    status_icon: str,
    user_name: str,
    user_email: str,
    event_type: str,
    time_str: str,
    address_text: str,
    extra_message: str = "",
) -> str:
    """Generate a beautiful HTML email template."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0; padding:0; background-color:#f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9; padding:30px 0;">
            <tr>
                <td align="center">
                    <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 2px 12px rgba(0,0,0,0.08);">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, {status_color}, #1e3a5f); padding:28px 24px; text-align:center;">
                                <div style="font-size:40px; margin-bottom:8px;">{status_icon}</div>
                                <h1 style="color:#ffffff; margin:0; font-size:22px; font-weight:700;">{title}</h1>
                                <p style="color:rgba(255,255,255,0.85); margin:6px 0 0; font-size:13px;">{event_type}</p>
                            </td>
                        </tr>

                        <!-- Body -->
                        <tr>
                            <td style="padding:24px;">
                                <!-- User Info -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
                                    <tr>
                                        <td style="background:#f8f9fb; border-radius:8px; padding:14px 16px;">
                                            <p style="margin:0 0 4px; font-size:11px; color:#8c95a6; text-transform:uppercase; letter-spacing:0.5px;">User</p>
                                            <p style="margin:0; font-size:15px; color:#1a1a2e; font-weight:600;">{user_name}</p>
                                            <p style="margin:2px 0 0; font-size:13px; color:#5a6577;">{user_email}</p>
                                        </td>
                                    </tr>
                                </table>

                                <!-- Time -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
                                    <tr>
                                        <td style="background:#f8f9fb; border-radius:8px; padding:14px 16px;">
                                            <p style="margin:0 0 4px; font-size:11px; color:#8c95a6; text-transform:uppercase; letter-spacing:0.5px;">⏰ Time (IST)</p>
                                            <p style="margin:0; font-size:15px; color:#1a1a2e; font-weight:600;">{time_str}</p>
                                        </td>
                                    </tr>
                                </table>

                                <!-- Location -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
                                    <tr>
                                        <td style="background:#f8f9fb; border-radius:8px; padding:14px 16px;">
                                            <p style="margin:0 0 4px; font-size:11px; color:#8c95a6; text-transform:uppercase; letter-spacing:0.5px;">📍 Location</p>
                                            <p style="margin:0; font-size:15px; color:#1a1a2e; font-weight:600;">{address_text}</p>
                                        </td>
                                    </tr>
                                </table>

                                {f'''
                                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
                                    <tr>
                                        <td style="background:#fff3f3; border:1px solid #fecaca; border-radius:8px; padding:14px 16px;">
                                            <p style="margin:0; font-size:13px; color:#b91c1c; line-height:1.5;">{extra_message}</p>
                                        </td>
                                    </tr>
                                </table>
                                ''' if extra_message else ''}
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background:#f8f9fb; padding:16px 24px; text-align:center; border-top:1px solid #eef0f3;">
                                <p style="margin:0; font-size:11px; color:#8c95a6;">
                                    🔒 FaceAuth Security Alert • This is an automated notification
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


async def send_auth_email(
    api_key: str,
    to_email: str,
    user_name: str,
    event: str,
    address: dict | None = None,
    extra_message: str = "",
):
    """
    Send an authentication event email.

    Args:
        api_key: Resend API key
        to_email: Recipient email
        user_name: User's full name
        event: One of 'register_success', 'register_fail', 'login_success', 'login_fail'
        address: Geocoded address dict (road, area, city, state, country, pincode)
        extra_message: Additional context (e.g., failure reason)
    """
    if not api_key:
        logger.warning("RESEND_API_KEY not set — skipping email notification")
        return

    time_str = _get_ist_time()
    address_text = _build_address_text(address)

    configs = {
        "register_success": {
            "title": "Registration Successful ✅",
            "subject": f"✅ FaceAuth — Registration Successful",
            "status_color": "#059669",
            "status_icon": "✅",
            "event_type": "New Account Registered",
        },
        "register_fail": {
            "title": "Registration Failed ❌",
            "subject": f"❌ FaceAuth — Registration Failed",
            "status_color": "#dc2626",
            "status_icon": "❌",
            "event_type": "Registration Attempt Failed",
        },
        "login_success": {
            "title": "Login Successful 🔓",
            "subject": f"🔓 FaceAuth — Login from {address.get('area', 'Unknown') if address else 'Unknown'}",
            "status_color": "#2563eb",
            "status_icon": "🔓",
            "event_type": "Successful Login",
        },
        "login_fail": {
            "title": "Login Failed 🚫",
            "subject": f"🚫 FaceAuth — Failed Login Attempt",
            "status_color": "#dc2626",
            "status_icon": "🚫",
            "event_type": "Failed Login Attempt",
        },
    }

    cfg = configs.get(event, configs["login_fail"])

    html = _email_template(
        title=cfg["title"],
        status_color=cfg["status_color"],
        status_icon=cfg["status_icon"],
        user_name=user_name,
        user_email=to_email,
        event_type=cfg["event_type"],
        time_str=time_str,
        address_text=address_text,
        extra_message=extra_message,
    )

    try:
        resend.api_key = api_key
        resend.Emails.send({
            "from": "FaceAuth <onboarding@resend.dev>",
            "to": [to_email],
            "subject": cfg["subject"],
            "html": html,
        })
        logger.info(f"Email sent: {event} → {to_email}")
    except Exception as e:
        logger.warning(f"Failed to send email ({event} → {to_email}): {e}")
