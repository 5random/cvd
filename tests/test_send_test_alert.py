import contextlib
import pytest

from cvd.gui.alt_application import SimpleGUIApplication
from cvd.utils.config_service import set_config_service
from cvd.utils.email_alert_service import set_email_alert_service


@pytest.mark.asyncio
async def test_send_test_alert_handles_exceptions(tmp_path, monkeypatch):
    cfg_dir = tmp_path
    (cfg_dir / "config.json").write_text("{}")
    (cfg_dir / "default_config.json").write_text("{}")

    class DummyDarkMode:
        def __init__(self, value=False, *, on_change=None):
            self.value = value

    monkeypatch.setattr("nicegui.ui.dark_mode", lambda *a, **k: DummyDarkMode())

    class DummyManager:
        _controllers = {}
        def get_controller(self, controller_id: str):
            return self._controllers.get(controller_id)

    monkeypatch.setattr(
        "cvd.controllers.controller_manager.create_cvd_controller_manager",
        lambda: DummyManager(),
    )

    class DummyEmailAlertService:
        def __init__(self, service):
            pass

    # patch email alert service globally
    email_mod = __import__(
        "cvd.utils.email_alert_service",
        fromlist=["EmailAlertService"],
    )
    monkeypatch.setattr(email_mod, "EmailAlertService", DummyEmailAlertService)

    app = SimpleGUIApplication(
        config_dir=cfg_dir,
        email_alert_service_cls=DummyEmailAlertService,
    )

    # ensure at least one active configuration
    app.alert_configurations = [
        {
            "name": "Test",
            "emails": ["a@example.com"],
            "settings": {"system_error": {"enabled": True}},
        }
    ]

    notifications = []

    def notifier(msg, **kw):
        notifications.append((msg, kw))

    monkeypatch.setattr("cvd.utils.ui_helpers.notify_later", notifier)
    monkeypatch.setattr("cvd.gui.alt_application.notify_later", notifier)

    async def failing_gather(tasks, *args, **kwargs):
        for t in tasks:
            with contextlib.suppress(Exception):
                await t
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "cvd.gui.alt_application.gather_with_concurrency", failing_gather
    )

    try:
        await app._send_test_to_all_configs()
    finally:
        set_config_service(None)

    assert notifications
    assert notifications[0][0].startswith(
        "Test alerts sent to 0 recipients"
    )

