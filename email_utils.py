import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM    = os.getenv("EMAIL_FROM", "noreply@vault-partners.eu")
BASE_URL      = os.getenv("BASE_URL", "http://localhost:8000")
APP_NAME      = os.getenv("APP_NAME", "Vault Partners")


def send_password_reset_email(to_email: str, token: str) -> bool:
    reset_link = f"{BASE_URL}/reset-password/{token}"
    print(f"\n[DEV] Password reset link for {to_email}:\n  {reset_link}\n")
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[DEV] SMTP not configured — email not sent, use the link above.")
        return False
    reset_link = f"{BASE_URL}/reset-password/{token}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
        <div style="background: white; padding: 40px; border-radius: 8px;">
            <h1 style="color: #1a1a2e; margin-bottom: 8px;">{APP_NAME}</h1>
            <hr style="border: 1px solid #eee; margin-bottom: 30px;">
            <h2 style="color: #333;">Password Reset Request</h2>
            <p style="color: #666; line-height: 1.6;">
                We received a request to reset your password. Click the button below to create a new password.
                This link will expire in <strong>1 hour</strong>.
            </p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_link}"
                   style="background: #c9a96e; color: white; padding: 14px 32px; text-decoration: none;
                          border-radius: 4px; font-weight: bold; font-size: 16px;">
                    Reset Password
                </a>
            </div>
            <p style="color: #999; font-size: 12px;">
                If you didn't request this, you can safely ignore this email.<br>
                Or copy this link: {reset_link}
            </p>
        </div>
    </body>
    </html>
    """

    text = f"Reset your password here: {reset_link}\n\nThis link expires in 1 hour."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{APP_NAME} — Password Reset"
        msg["From"]    = EMAIL_FROM
        msg["To"]      = to_email
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


def send_welcome_email(to_email: str, full_name: str) -> bool:
    print(f"\n[DEV] Welcome email would be sent to {to_email}\n")
    if not SMTP_USER or not SMTP_PASSWORD:
        return False
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
        <div style="background: white; padding: 40px; border-radius: 8px;">
            <h1 style="color: #1a1a2e; margin-bottom: 8px;">{APP_NAME}</h1>
            <hr style="border: 1px solid #eee; margin-bottom: 30px;">
            <h2 style="color: #333;">Welcome, {full_name}!</h2>
            <p style="color: #666; line-height: 1.6;">
                Your account has been created. You can now log in, set up your profile, and start adding projects.
            </p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{BASE_URL}/login"
                   style="background: #c9a96e; color: white; padding: 14px 32px; text-decoration: none;
                          border-radius: 4px; font-weight: bold; font-size: 16px;">
                    Go to Dashboard
                </a>
            </div>
        </div>
    </body>
    </html>
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Welcome to {APP_NAME}"
        msg["From"]    = EMAIL_FROM
        msg["To"]      = to_email
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False
