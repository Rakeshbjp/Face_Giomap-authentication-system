import smtplib
from email.message import EmailMessage
from app.config.settings import get_settings
import logging

logger = logging.getLogger(__name__)

def send_admin_email(subject: str, body: str):
    settings = get_settings()
    
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD or not settings.ADMIN_EMAIL:
        logger.warning("SMTP credentials or admin email not configured. Skipping email notification.")
        return False
        
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = settings.SMTP_USERNAME
        msg['To'] = settings.ADMIN_EMAIL

        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
            
        logger.info(f"Successfully sent admin email: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
