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

from program.src.utils.config_service import (
    ConfigurationService,
    set_config_service,
)
from program.src.utils.email_alert_service import EmailAlertService
from program.src.utils.log_service import info, warning, error


class ManualEmailAlertService(EmailAlertService):
    """EmailAlertService variant allowing custom sender and login."""

    def __init__(
        self,
        config_service: ConfigurationService,
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
        targets = recipient or self.recipients or ([] if self.recipient is None else [self.recipient])
        if isinstance(targets, str):
            targets = [targets]
        else:
            targets = list(targets)
        if not targets:
            warning("EmailAlertService: no recipient configured")
            return False

        try:
            smtp_conn = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) if self.smtp_use_ssl else smtplib.SMTP(self.smtp_host, self.smtp_port)
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


def load_config(config_dir: Path) -> ConfigurationService:
    """Initialise ConfigurationService from ``config_dir`` and return it."""
    cfg = ConfigurationService(
        config_path=config_dir / "config.json",
        default_config_path=config_dir / "default_config.json",
    )
    set_config_service(cfg)
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual test for EmailAlertService")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "program" / "config",
        help="Directory containing config.json and default_config.json",
    )
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

    cfg = load_config(args.config_dir)
    service = ManualEmailAlertService(
        cfg,
        sender_address=args.from_address,
        login_user=args.smtp_user,
        login_password=args.smtp_password,
    )
    if args.smtp_host:
        service.smtp_host = args.smtp_host
    if args.smtp_port:
        service.smtp_port = args.smtp_port

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
