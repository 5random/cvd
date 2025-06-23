import pytest
from cvd.gui.alt_application import SimpleGUIApplication
from cvd.utils.config_service import (
    get_config_service,
    set_config_service,
)
from cvd.utils.email_alert_service import set_email_alert_service


def test_global_services_set(tmp_path, monkeypatch):
    cfg_dir = tmp_path
    (cfg_dir / "config.json").write_text("{}")
    (cfg_dir / "default_config.json").write_text("{}")

    captured = {}

    class DummyManager:
        _controllers = {}

        def get_controller(self, controller_id: str):
            return self._controllers.get(controller_id)

    def dummy_create_manager():
        captured["config"] = get_config_service()
        return DummyManager()

    monkeypatch.setattr(
        "cvd.controllers.controller_manager.create_cvd_controller_manager",
        dummy_create_manager,
    )

    class DummyEmailAlertService:
        def __init__(self, service):
            self.service = service

    email_mod = __import__(
        "cvd.utils.email_alert_service",
        fromlist=["EmailAlertService"],
    )
    monkeypatch.setattr(email_mod, "EmailAlertService", DummyEmailAlertService)

    try:
        other_mod = __import__(
            "cvd.utils.email_alert_service",
            fromlist=["EmailAlertService"],
        )
        monkeypatch.setattr(other_mod, "EmailAlertService", DummyEmailAlertService)
    except ImportError:
        pass

    try:
        app = SimpleGUIApplication(
            config_dir=cfg_dir,
            email_alert_service_cls=DummyEmailAlertService,
        )
        assert get_config_service() is app.config_service
        assert isinstance(app.email_alert_service, DummyEmailAlertService)
        assert app.email_alert_service.service is app.config_service
        assert captured["config"] is app.config_service
    finally:
        set_config_service(None)


@pytest.mark.asyncio
async def test_startup_aborts_on_camera_failure(tmp_path, monkeypatch):
    cfg_dir = tmp_path
    (cfg_dir / "config.json").write_text("{}")
    (cfg_dir / "default_config.json").write_text("{}")

    class DummyCamera:
        async def test_camera_access(self):
            return False

    class DummyManager:
        def __init__(self):
            self._controllers = {"camera_capture": DummyCamera()}

        def get_controller(self, cid: str):
            return self._controllers.get(cid)

        async def start_all_controllers(self):
            raise AssertionError("should not start controllers")

    monkeypatch.setattr(
        "cvd.controllers.controller_manager.create_cvd_controller_manager",
        lambda: DummyManager(),
    )

    monkeypatch.setattr(
        "cvd.utils.concurrency.async_utils.install_signal_handlers", lambda *a, **k: None
    )

    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        "cvd.gui.alt_application.probe_camera_modes", AsyncMock(return_value=[])
    )

    notifications = []
    monkeypatch.setattr("nicegui.ui.notify", lambda msg, **kw: notifications.append(msg))

    app = SimpleGUIApplication(config_dir=cfg_dir, email_alert_service_cls=lambda s: None)

    await app.startup()

    assert notifications
    assert "camera" in notifications[0].lower()
