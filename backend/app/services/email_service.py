import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.config import settings


class EmailService:
    """Service for sending emails"""
    
    def __init__(self):
        self.smtp_server = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.EMAILS_FROM_EMAIL
        self.from_name = settings.EMAILS_FROM_NAME
        self.templates_dir = Path(__file__).parent.parent / "templates" / "emails"
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        cc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Send an email
        
        Args:
            to_email: Recipient email
            subject: Email subject
            html_content: HTML content
            text_content: Plain text content (optional)
            cc: CC recipients (optional)
            attachments: List of attachment dictionaries (optional)
            
        Returns:
            True if the email was sent successfully, False otherwise
        """
        # Skip sending emails if SMTP is not configured
        if not all([self.smtp_server, self.smtp_port, self.smtp_user, self.smtp_password]):
            logger.warning("SMTP not configured, skipping email sending")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            
            if cc:
                msg["Cc"] = ", ".join(cc)
            
            # Add text part
            if text_content:
                msg.attach(MIMEText(text_content, "plain"))
            
            # Add HTML part
            msg.attach(MIMEText(html_content, "html"))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    msg.attach(attachment)
            
            # Connect to server and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if settings.SMTP_TLS:
                    server.starttls()
                
                server.login(self.smtp_user, self.smtp_password)
                recipients = [to_email]
                if cc:
                    recipients.extend(cc)
                server.sendmail(self.from_email, recipients, msg.as_string())
            
            logger.info(f"Email sent to {to_email}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    async def send_password_reset(self, email: str, token: str) -> bool:
        """Send password reset email"""
        reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
        
        html_content = f"""
        <p>You requested a password reset for your EchoQuest account.</p>
        <p>Please click the link below to reset your password:</p>
        <p><a href="{reset_url}">{reset_url}</a></p>
        <p>This link will expire in 24 hours.</p>
        <p>If you didn't request a password reset, you can ignore this email.</p>
        """
        
        text_content = f"""
        You requested a password reset for your EchoQuest account.
        
        Please visit the following URL to reset your password:
        {reset_url}
        
        This link will expire in 24 hours.
        
        If you didn't request a password reset, you can ignore this email.
        """
        
        return await self.send_email(
            to_email=email,
            subject="Reset Your EchoQuest Password",
            html_content=html_content,
            text_content=text_content,
        )
    
    async def send_organization_invite(
        self, email: str, organization_name: str, invite_url: str
    ) -> bool:
        """Send organization invitation email"""
        html_content = f"""
        <p>You've been invited to join the <strong>{organization_name}</strong> organization on EchoQuest.</p>
        <p>Please click the link below to accept the invitation:</p>
        <p><a href="{invite_url}">{invite_url}</a></p>
        <p>This invitation will expire in 7 days.</p>
        """
        
        text_content = f"""
        You've been invited to join the {organization_name} organization on EchoQuest.
        
        Please visit the following URL to accept the invitation:
        {invite_url}
        
        This invitation will expire in 7 days.
        """
        
        return await self.send_email(
            to_email=email,
            subject=f"Invitation to Join {organization_name} on EchoQuest",
            html_content=html_content,
            text_content=text_content,
        )
    
    async def send_welcome_email(self, email: str, name: str) -> bool:
        """Send welcome email to new user"""
        html_content = f"""
        <p>Welcome to EchoQuest, {name}!</p>
        <p>Thank you for creating an account. We're excited to help you analyze your interviews.</p>
        <p>To get started, log in to your account and create your first questionnaire or interview.</p>
        <p><a href="{settings.FRONTEND_URL}/login">Sign in to EchoQuest</a></p>
        """
        
        text_content = f"""
        Welcome to EchoQuest, {name}!
        
        Thank you for creating an account. We're excited to help you analyze your interviews.
        
        To get started, log in to your account and create your first questionnaire or interview.
        
        {settings.FRONTEND_URL}/login
        """
        
        return await self.send_email(
            to_email=email,
            subject="Welcome to EchoQuest",
            html_content=html_content,
            text_content=text_content,
        )
    
    async def send_interview_complete_notification(
        self, email: str, name: str, interview_title: str, interview_url: str
    ) -> bool:
        """Send notification when interview processing is complete"""
        html_content = f"""
        <p>Hello {name},</p>
        <p>Your interview <strong>{interview_title}</strong> has been successfully processed and is now ready for analysis.</p>
        <p><a href="{interview_url}">View Interview Results</a></p>
        """
        
        text_content = f"""
        Hello {name},
        
        Your interview "{interview_title}" has been successfully processed and is now ready for analysis.
        
        View Interview Results: {interview_url}
        """
        
        return await self.send_email(
            to_email=email,
            subject=f"Interview Processing Complete: {interview_title}",
            html_content=html_content,
            text_content=text_content,
        )


# Create singleton instance
email_service = EmailService()