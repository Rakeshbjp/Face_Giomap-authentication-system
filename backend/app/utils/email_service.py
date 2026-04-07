# pyre-ignore-all-errors
"""
Email notification service using Resend API.
Sends real-time emails for registration and login events.
"""

import logging
from datetime import datetime, timezone, timedelta
import httpx

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


def _format_time_ist() -> str:
    """Return current time formatted in IST."""
    now = datetime.now(IST)
    return now.strftime("%d %b %Y, %I:%M:%S %p IST")


def _build_location_html(address: dict | None, coords: dict | None) -> str:
    """Build a nice HTML snippet for location info."""
    if not address and not coords:
        return "<p style='color:#888;'>Location not available</p>"

    parts = []
    if address:
        if address.get("road"):
            parts.append(f"<strong>{address['road']}</strong>")
        if address.get("area"):
            area_str = address["area"]
            if address.get("suburb") and address["suburb"] != address["area"]:
                area_str += f", {address['suburb']}"
            parts.append(area_str)
        city_state = ", ".join(filter(None, [
            address.get("city"),
            address.get("state"),
            address.get("country"),
        ]))
        if city_state:
            parts.append(city_state)
        if address.get("pincode"):
            parts.append(f"PIN: {address['pincode']}")

    location_html = "<br>".join(parts) if parts else ""

    if coords:
        location_html += (
            f"<br><span style='color:#888;font-size:12px;'>"
            f"GPS: {coords.get('latitude', 0):.6f}, {coords.get('longitude', 0):.6f}"
            f"</span>"
        )

    return location_html


async def _send_email(to: str, subject: str, html: str):
    """Send an email via Resend API (fire-and-forget, never blocks auth flow)."""
    settings = get_settings()
    api_key = settings.RESEND_API_KEY

    if not api_key:
        logger.warning("RESEND_API_KEY not set — skipping email")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.RESEND_FROM_EMAIL,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
            )
            if response.status_code in (200, 201):
                logger.info(f"Email sent to {to}: {subject}")
            else:
                logger.warning(f"Resend API error ({response.status_code}): {response.text}")
    except Exception as e:
        logger.warning(f"Failed to send email to {to}: {e}")


# ──────────────────────────────────────────────
#  Public email functions
# ──────────────────────────────────────────────

async def send_registration_success_email(
    name: str, email: str, address: dict | None = None, coords: dict | None = None
):
    """Email sent after successful registration."""
    time_str = _format_time_ist()
    location_html = _build_location_html(address, coords)

    html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;border-radius:12px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#2563eb,#4f46e5);padding:32px 24px;text-align:center;">
        <h1 style="color:white;margin:0;font-size:24px;">✅ Registration Successful</h1>
        <p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:14px;">FaceAuth Security System</p>
      </div>
      <div style="padding:24px;">
        <p style="font-size:16px;color:#1e293b;">Hello <strong>{name}</strong>,</p>
        <p style="color:#475569;">Your account has been successfully registered on FaceAuth.</p>
        
        <div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:16px 0;">
          <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="padding:8px 0;color:#64748b;width:140px;">📧 Email</td><td style="color:#1e293b;font-weight:600;">{email}</td></tr>
            <tr><td style="padding:8px 0;color:#64748b;">🕐 Registered At</td><td style="color:#1e293b;font-weight:600;">{time_str}</td></tr>
            <tr><td style="padding:8px 0;color:#64748b;vertical-align:top;">📍 Location</td><td style="color:#1e293b;">{location_html}</td></tr>
          </table>
        </div>
        
        <p style="color:#475569;font-size:13px;">Your location has been locked for security. You can only login from within 100m of this registered location.</p>
        <p style="color:#94a3b8;font-size:12px;margin-top:24px;">— FaceAuth Security Team</p>
      </div>
    </div>
    """
    await _send_email(email, "✅ Registration Successful — FaceAuth", html)


async def send_registration_failed_email(
    email: str, reason: str, address: dict | None = None, coords: dict | None = None
):
    """Email sent after failed registration."""
    time_str = _format_time_ist()
    location_html = _build_location_html(address, coords)

    html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;border-radius:12px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#dc2626,#b91c1c);padding:32px 24px;text-align:center;">
        <h1 style="color:white;margin:0;font-size:24px;">❌ Registration Failed</h1>
        <p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:14px;">FaceAuth Security Alert</p>
      </div>
      <div style="padding:24px;">
        <p style="font-size:16px;color:#1e293b;">Hello,</p>
        <p style="color:#475569;">A registration attempt was made with your email address but it failed.</p>
        
        <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:16px;margin:16px 0;">
          <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="padding:8px 0;color:#64748b;width:140px;">📧 Email</td><td style="color:#1e293b;font-weight:600;">{email}</td></tr>
            <tr><td style="padding:8px 0;color:#64748b;">🕐 Attempted At</td><td style="color:#1e293b;font-weight:600;">{time_str}</td></tr>
            <tr><td style="padding:8px 0;color:#64748b;">❌ Reason</td><td style="color:#dc2626;font-weight:600;">{reason}</td></tr>
            <tr><td style="padding:8px 0;color:#64748b;vertical-align:top;">📍 Location</td><td style="color:#1e293b;">{location_html}</td></tr>
          </table>
        </div>
        
        <p style="color:#475569;font-size:13px;">If this was not you, please ignore this email. No account was created.</p>
        <p style="color:#94a3b8;font-size:12px;margin-top:24px;">— FaceAuth Security Team</p>
      </div>
    </div>
    """
    await _send_email(email, "❌ Registration Failed — FaceAuth", html)


async def send_login_success_email(
    name: str, email: str, address: dict | None = None, coords: dict | None = None
):
    """Email sent after successful login."""
    time_str = _format_time_ist()
    location_html = _build_location_html(address, coords)

    html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;border-radius:12px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#16a34a,#15803d);padding:32px 24px;text-align:center;">
        <h1 style="color:white;margin:0;font-size:24px;">🔓 Login Successful</h1>
        <p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:14px;">FaceAuth Security Notification</p>
      </div>
      <div style="padding:24px;">
        <p style="font-size:16px;color:#1e293b;">Hello <strong>{name}</strong>,</p>
        <p style="color:#475569;">You have successfully logged into your FaceAuth account.</p>
        
        <div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:16px 0;">
          <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="padding:8px 0;color:#64748b;width:140px;">👤 Name</td><td style="color:#1e293b;font-weight:600;">{name}</td></tr>
            <tr><td style="padding:8px 0;color:#64748b;">📧 Email</td><td style="color:#1e293b;font-weight:600;">{email}</td></tr>
            <tr><td style="padding:8px 0;color:#64748b;">🕐 Login Time</td><td style="color:#1e293b;font-weight:600;">{time_str}</td></tr>
            <tr><td style="padding:8px 0;color:#64748b;vertical-align:top;">📍 Logged in from</td><td style="color:#1e293b;">{location_html}</td></tr>
          </table>
        </div>
        
        <p style="color:#475569;font-size:13px;">If this login was not performed by you, please change your password immediately and re-register your account.</p>
        <p style="color:#94a3b8;font-size:12px;margin-top:24px;">— FaceAuth Security Team</p>
      </div>
    </div>
    """
    await _send_email(email, "🔓 Login Successful — FaceAuth", html)


async def send_login_failed_email(
    email: str, reason: str, address: dict | None = None, coords: dict | None = None
):
    """Email sent after failed login attempt."""
    time_str = _format_time_ist()
    location_html = _build_location_html(address, coords)

    html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;border-radius:12px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#ea580c,#c2410c);padding:32px 24px;text-align:center;">
        <h1 style="color:white;margin:0;font-size:24px;">⚠️ Login Attempt Failed</h1>
        <p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:14px;">FaceAuth Security Alert</p>
      </div>
      <div style="padding:24px;">
        <p style="font-size:16px;color:#1e293b;">Hello,</p>
        <p style="color:#475569;">A failed login attempt was detected on your FaceAuth account.</p>
        
        <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:16px;margin:16px 0;">
          <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="padding:8px 0;color:#64748b;width:140px;">📧 Email</td><td style="color:#1e293b;font-weight:600;">{email}</td></tr>
            <tr><td style="padding:8px 0;color:#64748b;">🕐 Attempted At</td><td style="color:#1e293b;font-weight:600;">{time_str}</td></tr>
            <tr><td style="padding:8px 0;color:#64748b;">❌ Reason</td><td style="color:#ea580c;font-weight:600;">{reason}</td></tr>
            <tr><td style="padding:8px 0;color:#64748b;vertical-align:top;">📍 Attempted from</td><td style="color:#1e293b;">{location_html}</td></tr>
          </table>
        </div>
        
        <p style="color:#475569;font-size:13px;">If this was not you, someone may be trying to access your account. Consider changing your password.</p>
        <p style="color:#94a3b8;font-size:12px;margin-top:24px;">— FaceAuth Security Team</p>
      </div>
    </div>
    """
    await _send_email(email, "⚠️ Failed Login Attempt — FaceAuth", html)
