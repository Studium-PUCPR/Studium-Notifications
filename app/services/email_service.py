import logging
from typing import Any, Dict, Optional
import boto3
from app.config import Settings, get_settings
from app.models.notification import NotificationItem

logger = logging.getLogger("studium.notifications.email")


class EmailService:
    """Dispatches emails via Amazon SES or logs simulated email delivery."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.simulate = self.settings.simulate_ses_email
        self.sender = self.settings.ses_sender_email

        if not self.simulate:
            kwargs: Dict[str, Any] = {"region_name": self.settings.aws_region}
            if self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
                kwargs["aws_access_key_id"] = self.settings.aws_access_key_id
                kwargs["aws_secret_access_key"] = self.settings.aws_secret_access_key
            self.ses_client = boto3.client("ses", **kwargs)
        else:
            self.ses_client = None

    def send_notification_email(self, item: NotificationItem, recipient_email: Optional[str] = None) -> bool:
        """
        Sends an email alert corresponding to the notification.
        """
        recipient = recipient_email or f"{item.user_id}@pucpr.edu.br"
        subject = f"[Studium] {item.title}"
        body_text = f"Olá,\n\n{item.message}\n\nAtenciosamente,\nEquipe Studium PUCPR"

        if self.simulate:
            logger.info(
                f"[SIMULATED SES DISPATCH] To: {recipient} | Subject: '{subject}' | Type: {item.type.value}"
            )
            return True

        try:
            self.ses_client.send_email(
                Source=self.sender,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
                },
            )
            logger.info(f"SES email successfully dispatched to '{recipient}'.")
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch SES email to '{recipient}': {e}")
            return False
