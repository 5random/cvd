#!/usr/bin/env python3
"""Manual test script for EmailAlertService.

This script sends a couple of test emails using :class:`EmailAlertService`.
It supports overriding the SMTP configuration on the command line so
that different accounts can be used without modifying ``config.json``.
It exercises the main
features of :class:`EmailAlertService`:

- plain text mail
- mail with additional status text
- mail with JPEG image attachment

The script is intended for manual execution by developers. Either edit
the configuration file or provide the SMTP details via command line
arguments.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Iterable
import sys

# Only adjust ``sys.path`` when executed directly so that ``src`` is importable
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    # Ensure 'cvd' package (under src) is importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


from src.cvd.utils.email_alert_service import EmailAlertService
from src.cvd.utils.log_service import info, warning, error


DEFAULT_CONFIG = {
    "alerting": {
        "email_recipient": "willem.dittloff@tuhh.de",
        "smtp_host": "mail.tuhh.de",
        "smtp_port": 25,
        "smtp_user": "willem.dittloff@tuhh.de",
        "smtp_password": "",
        "smtp_use_ssl": False,
        "critical_state_timeout_s": 60,
    }
}


class SimpleConfigService:
    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg

    def get(self, path: str, _type=None, default=None):
        value = self._cfg
        for key in path.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        if _type is not None and not isinstance(value, _type):
            return default
        return value


class ManualEmailAlertService(EmailAlertService):
    """EmailAlertService variant allowing custom sender and login."""

    def __init__(
        self,
        config_service,
        *,
        sender_address: str | None = None,
        login_user: str | None = None,
        login_password: str | None = None,
    ) -> None:
        super().__init__(config_service)
        self.sender_address = sender_address or self.smtp_user
        self.login_user = login_user or self.smtp_user
        self.login_password = login_password or self.smtp_password

    def send_alert(
        self,
        subject: str,
        body: str,
        recipient: str | Iterable[str] | None = None,
        *,
        status_text: str | None = None,
        image_attachment: bytes | None = None,
    ) -> bool:
        targets = (
            recipient
            or self.recipients
            or ([] if self.recipient is None else [self.recipient])
        )
        if isinstance(targets, str):
            targets = [targets]
        else:
            targets = list(targets)
        if not targets:
            warning("EmailAlertService: no recipient configured")
            return False

        try:
            smtp_conn = (
                smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
                if self.smtp_use_ssl
                else smtplib.SMTP(self.smtp_host, self.smtp_port)
            )
            with smtp_conn as smtp:
                if hasattr(smtp, "ehlo"):
                    smtp.ehlo()
                if not self.smtp_use_ssl:
                    smtp.starttls()
                    if hasattr(smtp, "ehlo"):
                        smtp.ehlo()
                if self.login_user and self.login_password:
                    smtp.login(self.login_user, self.login_password)
                for addr in targets:
                    msg = EmailMessage()
                    msg["Subject"] = subject
                    msg["From"] = self.sender_address or self.smtp_user or "cvd-tracker"
                    msg["To"] = addr
                    full_body = body
                    if status_text:
                        full_body += f"\n\n{status_text}"
                    msg.set_content(full_body)
                    if image_attachment is not None:
                        msg.add_attachment(
                            image_attachment,
                            maintype="image",
                            subtype="jpeg",
                            filename="attachment.jpg",
                        )
                    smtp.send_message(msg)
                    info(f"Sent alert email to {addr}")
                    self._history.append(
                        {
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "recipient": addr,
                            "subject": subject,
                            "attachment": bool(image_attachment),
                        }
                    )
            return True
        except Exception as exc:
            error(f"Failed to send alert email: {exc}")
            return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual test for EmailAlertService")
    parser.add_argument(
        "--image",
        type=Path,
        help="Optional path to a JPEG image to attach to the third test mail",
    )
    parser.add_argument(
        "--recipient",
        help="Override recipient email address from configuration",
    )
    parser.add_argument("--smtp-host", help="SMTP server host to use")
    parser.add_argument("--smtp-port", type=int, help="SMTP server port")
    parser.add_argument("--smtp-user", help="SMTP username")
    parser.add_argument("--smtp-password", help="SMTP password")
    parser.add_argument(
        "--from-address",
        help="Sender address to appear in emails (defaults to SMTP user)",
    )
    parser.add_argument(
        "--signature",
        help="Optional signature appended to all messages",
    )
    args = parser.parse_args()

    cfg_dict = DEFAULT_CONFIG.copy()
    service = ManualEmailAlertService(
        SimpleConfigService(cfg_dict),
        sender_address=args.from_address,
        login_user=args.smtp_user,
        login_password=args.smtp_password,
    )
    if args.smtp_host:
        service.smtp_host = args.smtp_host
    if args.smtp_port:
        service.smtp_port = args.smtp_port

    # Prompt for SMTP password if not provided (required for authenticated servers)
    if service.login_user and not service.login_password:
        import getpass

        service.login_password = getpass.getpass(
            f"SMTP password for user {service.login_user}: "
        )

    image_bytes = None
    if args.image:
        image_bytes = args.image.read_bytes()

    signature = f"\n\n{args.signature}" if args.signature else ""

    print("Sending plain text email...")
    service.send_alert(
        "EmailAlertService test: plain text",
        f"This is a plain text test email.{signature}",
        recipient=args.recipient,
    )

    print("Sending email with status text...")
    service.send_alert(
        "EmailAlertService test: status",
        f"This message contains additional status text.{signature}",
        status_text="System running normally.",
        recipient=args.recipient,
    )

    if image_bytes:
        print("Sending email with image attachment...")
        service.send_alert(
            "EmailAlertService test: image",
            f"This message includes an image attachment.{signature}",
            image_attachment=image_bytes,
            recipient=args.recipient,
        )

    print("\nSent emails:")
    for item in service.get_history():
        print(item)


if __name__ == "__main__":
    main()
