"""
Email service for sending password reset emails and other notifications.
"""

from __future__ import annotations

import os
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


# Email configuration - in production, use environment variables
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")  # Your email
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # Your app password
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


async def send_password_reset_email(email: str, reset_token: str, user_name: Optional[str] = None) -> bool:
    """
    Send password reset email with a link containing the reset token.
    
    Args:
        email: Recipient email address
        reset_token: Password reset token
        user_name: Optional user name for personalization
    
    Returns:
        True if email was sent successfully, False otherwise
    """
    # If SMTP is not configured, skip sending (for development)
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[DEV MODE] Password reset email would be sent to {email}")
        print(f"[DEV MODE] Reset URL: {FRONTEND_URL}/reset-password.html?token=***&email={email}")
        # Note: Token is intentionally NOT logged for security
        return True
    
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["From"] = FROM_EMAIL
        message["To"] = email
        message["Subject"] = "Reset Your LibraryHub Password"
        
        # Create reset URL
        reset_url = f"{FRONTEND_URL}/reset-password.html?token={reset_token}&email={email}"
        
        # Create email body
        name = user_name or "User"
        
        text_content = f"""
Hello {name},

You requested to reset your password for your LibraryHub account.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request a password reset, please ignore this email.

Best regards,
LibraryHub Team
        """
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #3A86FF; color: white; text-decoration: none; border-radius: 8px; margin: 20px 0; }}
        .button:hover {{ background-color: #2563eb; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Reset Your LibraryHub Password</h2>
        <p>Hello {name},</p>
        <p>You requested to reset your password for your LibraryHub account.</p>
        <p>Click the button below to reset your password:</p>
        <a href="{reset_url}" class="button">Reset Password</a>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #666;">{reset_url}</p>
        <p><strong>This link will expire in 1 hour.</strong></p>
        <p>If you did not request a password reset, please ignore this email.</p>
        <div class="footer">
            <p>Best regards,<br>LibraryHub Team</p>
        </div>
    </div>
</body>
</html>
        """
        
        # Attach parts
        message.attach(MIMEText(text_content, "plain"))
        message.attach(MIMEText(html_content, "html"))
        
        # Send email
        await aiosmtplib.send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            start_tls=True,
        )
        
        return True
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False



