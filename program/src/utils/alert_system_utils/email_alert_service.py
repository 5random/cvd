"""Email alerting service for critical controller states."""
import smtplib
from email.message import EmailMessage
from typing import Optional

from src.utils.config_utils.config_service import get_config_service, ConfigurationService
from src.utils.log_utils.log_service import info, warning, error


class EmailAlertService:
    """Simple service for sending alert e-mails using SMTP."""

    def __init__(self, config_service: Optional[ConfigurationService] = None) -> None:
        self._config_service = config_service or get_config_service()
        if self._config_service is None:
            raise ValueError("Configuration service not available")
        self._load_configuration()

    def _load_configuration(self) -> None:
        cfg = self._config_service.get('alerting', dict, {}) or {}
        self.recipient: Optional[str] = cfg.get('email_recipient')
        self.smtp_host: str = cfg.get('smtp_host', 'localhost')
        self.smtp_port: int = cfg.get('smtp_port', 25)
        self.smtp_user: Optional[str] = cfg.get('smtp_user')
        self.smtp_password: Optional[str] = cfg.get('smtp_password')
        self.critical_timeout: int = cfg.get('critical_state_timeout_s', 60)

    def send_alert(self, subject: str, body: str) -> bool:
        """Send an alert e-mail. Returns True on success."""
        if not self.recipient:
            warning("EmailAlertService: no recipient configured")
            return False
        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = self.smtp_user or 'cvd-tracker'
            msg['To'] = self.recipient
            msg.set_content(body)
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
                if self.smtp_user:
                    smtp.starttls()
                    smtp.login(self.smtp_user, self.smtp_password or '')
                smtp.send_message(msg)
            info(f"Sent alert email to {self.recipient}")
            return True
        except Exception as exc:
            error(f"Failed to send alert email: {exc}")
            return False


_email_alert_service_instance: Optional[EmailAlertService] = None


def get_email_alert_service() -> Optional[EmailAlertService]:
    """Return the global :class:`EmailAlertService` instance."""
    global _email_alert_service_instance
    if _email_alert_service_instance is None:
        try:
            _email_alert_service_instance = EmailAlertService()
        except Exception as exc:
            error(f"Failed to create email alert service: {exc}")
            return None
    return _email_alert_service_instance


def set_email_alert_service(service: EmailAlertService) -> None:
    """Set the global :class:`EmailAlertService` instance."""
    global _email_alert_service_instance
    _email_alert_service_instance = service