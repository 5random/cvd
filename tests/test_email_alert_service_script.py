import sys
from email.message import EmailMessage
from types import SimpleNamespace


from scripts.email_alert_service_testing import (
    ManualEmailAlertService,
    SimpleConfigService,
    DEFAULT_CONFIG,
    main,
)
from experiment_manager import ExperimentState


class DummySMTP:
    """Collects sent messages for verification."""

    instances: list["DummySMTP"] = []

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sent_messages: list[EmailMessage] = []
        DummySMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def ehlo(self):
        pass

    def starttls(self):
        pass

    def login(self, user, password):
        self.login_user = user
        self.login_password = password

    def send_message(self, msg: EmailMessage):
        self.sent_messages.append(msg)


def test_send_alert_builds_message(monkeypatch):
    DummySMTP.instances.clear()
    monkeypatch.setattr("smtplib.SMTP", DummySMTP)
    monkeypatch.setattr("smtplib.SMTP_SSL", DummySMTP)
    monkeypatch.setattr(
        "cvd.utils.email_alert_service.get_experiment_manager",
        lambda: SimpleNamespace(get_current_state=lambda: ExperimentState.RUNNING),
    )

    service = ManualEmailAlertService(SimpleConfigService(DEFAULT_CONFIG.copy()))
    result = service.send_alert("Test", "Body", recipient="dest@example.com")

    assert result is True
    assert DummySMTP.instances
    smtp = DummySMTP.instances[-1]
    assert len(smtp.sent_messages) == 1
    msg = smtp.sent_messages[0]
    assert isinstance(msg, EmailMessage)
    assert msg["To"] == "dest@example.com"
    assert msg["Subject"] == "Test"


def test_main_argument_parsing(monkeypatch):
    DummySMTP.instances.clear()
    monkeypatch.setattr("smtplib.SMTP", DummySMTP)
    monkeypatch.setattr("smtplib.SMTP_SSL", DummySMTP)
    monkeypatch.setattr(
        "cvd.utils.email_alert_service.get_experiment_manager",
        lambda: SimpleNamespace(get_current_state=lambda: ExperimentState.RUNNING),
    )

    monkeypatch.setattr(sys, "argv", ["script", "--recipient", "dest@example.com"])
    main()

    total_sent = sum(len(inst.sent_messages) for inst in DummySMTP.instances)
    assert total_sent == 2
