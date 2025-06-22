"""Email alerting service for critical controller states."""
import smtplib
from email.message import EmailMessage
from typing import Optional, List, Dict, Iterable, Union
from datetime import datetime

from program.src.utils.config_service import get_config_service, ConfigurationService, ConfigurationError
from program.src.utils.log_service import info, warning, error


class EmailAlertService:
    """Simple service for sending alert e-mails using SMTP."""

    def __init__(self, config_service: Optional[ConfigurationService] = None) -> None:
        self._config_service = config_service or get_config_service()
        if self._config_service is None:
            raise ValueError("Configuration service not available")
        self._load_configuration()
        self._history: List[Dict[str, str]] = []

    @property
    def recipient(self) -> Optional[str]:
        return self.recipients[0] if self.recipients else None

    @recipient.setter
    def recipient(self, value: Optional[str]) -> None:
        self.recipients = [value] if value else None

    def _load_configuration(self) -> None:
        assert self._config_service is not None, "Configuration service not available"
        cfg = self._config_service.get('alerting', dict, {}) or {}
        self.recipient: Optional[str] = cfg.get('email_recipient')
        self.recipients: Optional[List[str]] = (
            [self.recipient] if self.recipient else None
        )
        self.smtp_host: str = cfg.get('smtp_host', 'localhost')
        self.smtp_port: int = cfg.get('smtp_port', 25)
        self.smtp_user: Optional[str] = cfg.get('smtp_user')
        self.smtp_password: Optional[str] = cfg.get('smtp_password')
        # Use SSL connection if True, else use STARTTLS on standard SMTP
        self.smtp_use_ssl: bool = cfg.get('smtp_use_ssl', False)
        self.critical_timeout: int = cfg.get('critical_state_timeout_s', 60)

        # Validate configuration and fall back to safe defaults rather than raising
        if not self.recipient or not isinstance(self.recipient, str) or not self.recipient.strip():
            warning("EmailAlertService: email recipient not configured; alert emails disabled")
            self.recipient = None
        if not isinstance(self.smtp_host, str) or not self.smtp_host.strip():
            warning("EmailAlertService: invalid smtp_host; using 'localhost'")
            self.smtp_host = 'localhost'
        if not isinstance(self.smtp_port, int) or not (1 <= self.smtp_port <= 65535):
            warning("EmailAlertService: invalid smtp_port; using 25")
            self.smtp_port = 25

    def send_alert(
        self,
        subject: str,
        body: str,
        recipient: Optional[Union[str, Iterable[str]]] = None,
        *,
        status_text: Optional[str] = None,
        image_attachment: Optional[bytes] = None,
    ) -> bool:
        """Send an alert e-mail. Returns True on success.

        Args:
            subject: Email subject
            body: Email body
            recipient: Optional override for the configured recipient
            status_text: Optional additional status text appended to body
            image_attachment: Optional JPEG image bytes to attach
        """
        target = recipient or self.recipients or ([] if self.recipient is None else [self.recipient])
        if isinstance(target, str):
            targets = [target]
        else:
            targets = list(target)
        if not targets:
            warning("EmailAlertService: no recipient configured")
            return False
        try:
            # Establish connection: SSL or plain
            if self.smtp_use_ssl:
                smtp_conn = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                smtp_conn = smtplib.SMTP(self.smtp_host, self.smtp_port)
            with smtp_conn as smtp:
                if hasattr(smtp, "ehlo"):
                    smtp.ehlo()
                if not self.smtp_use_ssl:
                    smtp.starttls()
                    if hasattr(smtp, "ehlo"):
                        smtp.ehlo()
                # Authenticate only if both user and password provided
                if self.smtp_user and self.smtp_password:
                    smtp.login(self.smtp_user, self.smtp_password)
                for addr in targets:
                    msg = EmailMessage()
                    msg['Subject'] = subject
                    msg['From'] = self.smtp_user or 'cvd-tracker'
                    msg['To'] = addr
                    full_body = body
                    if status_text:
                        full_body += f"\n\n{status_text}"
                    msg.set_content(full_body)
                    if image_attachment is not None:
                        msg.add_attachment(
                            image_attachment,
                            maintype='image',
                            subtype='jpeg',
                            filename='attachment.jpg',
                        )
                    smtp.send_message(msg)
                    info(f"Sent alert email to {addr}")
                    self._history.append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "recipient": addr,
                        "subject": subject,
                        "attachment": bool(image_attachment),
                    })
            return True
        except Exception as exc:
            error(f"Failed to send alert email: {exc}")
            return False

    def get_history(self, limit: int = 50) -> List[Dict[str, str]]:
        """Return a list of recently sent alerts."""
        return self._history[-limit:]


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
