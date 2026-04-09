import asyncio
from app.services.email_service import send_admin_email

def test():
    print("Testing email send...")
    success = send_admin_email("Test Alert from FastAPI", "If you receive this, SMTP is working perfectly!")
    if success:
        print("Success! Email sent. Check your inbox.")
    else:
        print("Failed to send email. Check error logs.")

if __name__ == "__main__":
    test()
