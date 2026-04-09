from fastapi import APIRouter, Request, HTTPException, Depends
from svix.webhooks import Webhook
from app.config.settings import get_settings
from app.services.email_service import send_admin_email
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.post("/clerk")
async def clerk_webhook(request: Request):
    settings = get_settings()
    
    if not settings.CLERK_WEBHOOK_SECRET:
        logger.error("CLERK_WEBHOOK_SECRET is not set in environment.")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
        
    payload = await request.body()
    headers = request.headers
    
    svix_id = headers.get("svix-id")
    svix_timestamp = headers.get("svix-timestamp")
    svix_signature = headers.get("svix-signature")
    
    if not svix_id or not svix_timestamp or not svix_signature:
        raise HTTPException(status_code=400, detail="Missing svix headers")
        
    try:
        wh = Webhook(settings.CLERK_WEBHOOK_SECRET)
        evt = wh.verify(payload, headers)
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    event_type = evt.get("type", "")
    data = evt.get("data", {})
    
    # Process Registration Event
    if event_type == "user.created":
        email_addresses = data.get("email_addresses", [])
        primary_email = email_addresses[0]["email_address"] if email_addresses else "Unknown"
        user_id = data.get("id")
        
        subject = "New User Registered via Clerk!"
        body = f"A new user has registered.\n\nUser ID: {user_id}\nEmail: {primary_email}"
        send_admin_email(subject, body)
        logger.info(f"Processed user.created event for {primary_email}")
        
    # Process Login Event
    elif event_type == "session.created":
        user_id = data.get("user_id")
        session_id = data.get("id")
        
        subject = "User Logged In via Clerk"
        body = f"A user just logged into the application.\n\nUser ID: {user_id}\nSession ID: {session_id}"
        send_admin_email(subject, body)
        logger.info(f"Processed session.created event for {user_id}")

    return {"success": True}
