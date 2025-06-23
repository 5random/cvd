import types
from pathlib import Path

import numpy as np
import pytest
from nicegui import Client, app
from cvd.controllers.controller_base import ControllerStatus


class DummyConfigService:
    def __init__(self) -> None:
        self.config_path = Path("dummy.json")

    def get(self, _path: str, expected_type=None, default=None):
        return default


class DummyControllerManager:
    def get_controller(self, _cid: str):
        return None


@pytest.mark.asyncio
async def test_video_feed_multiple_connections(monkeypatch):
    import importlib
    import sys

    fake_alert_mod = types.ModuleType("alert_element_new")
    fake_alert_mod.create_compact_alert_widget = lambda *a, **k: None
    fake_alert_mod.create_demo_configurations = lambda *a, **k: []
    fake_alert_mod.create_email_alert_status_display = lambda *a, **k: None
    fake_alert_mod.create_email_alert_wizard = lambda *a, **k: None
    fake_alert_mod.load_alert_configs = lambda *a, **k: []
    fake_alert_mod.save_alert_configs = lambda *a, **k: None

    class EmailAlertStatusDisplay:
        def __init__(self, *a, **k) -> None:
            self.update_callback = None

    fake_alert_mod.EmailAlertStatusDisplay = EmailAlertStatusDisplay
    sys.modules["cvd.gui.alt_gui_elements.alert_element_new"] = fake_alert_mod

    SimpleGUIApplication = importlib.import_module(
        "cvd.gui.alt_application"
    ).SimpleGUIApplication

    monkeypatch.setattr(
        "cvd.gui.alt_application.load_alert_configs", lambda *a, **k: []
    )
    monkeypatch.setattr(
        "cvd.gui.alt_application.create_demo_configurations", lambda: []
    )
    monkeypatch.setattr(
        "cvd.gui.alt_application.EmailAlertStatusDisplay",
        lambda *a, **k: types.SimpleNamespace(update_callback=None),
    )

    async def fake_generate(*_a, request=None, **_k):
        while True:
            if request and await request.is_disconnected():
                break
            yield b"x"

    monkeypatch.setattr("cvd.gui.alt_application.generate_mjpeg_stream", fake_generate)

    app_instance = SimpleGUIApplication(
        controller_manager=DummyControllerManager(),
        config_service=DummyConfigService(),
    )
    with Client.auto_index_client:
        app_instance.register_components()

    class DummyCam:
        def __init__(self) -> None:
            self.started = 0
            self.stopped = 0
            self.cleaned = 0
            self.status = ControllerStatus.STOPPED

        async def start(self) -> bool:
            self.started += 1
            self.status = ControllerStatus.RUNNING
            return True

        def get_output(self):
            return np.zeros((10, 10, 3), dtype=np.uint8)

        async def stop(self):
            self.stopped += 1
            self.status = ControllerStatus.STOPPED

        async def cleanup(self):
            self.cleaned += 1

    cam = DummyCam()
    app_instance.camera_controller = cam

    calls: list[bool] = []

    def fake_update(self, active: bool):
        calls.append(active)

    monkeypatch.setattr(
        SimpleGUIApplication, "update_camera_status", fake_update, raising=False
    )

    route = [r for r in app.routes if getattr(r, "path", None) == "/video_feed"][0]
    endpoint = route.endpoint.__wrapped__

    class DummyRequest:
        def __init__(self) -> None:
            self.disconnect = False

        async def is_disconnected(self):
            return self.disconnect

    req1 = DummyRequest()
    req2 = DummyRequest()

    resp1 = await endpoint(request=req1)
    resp2 = await endpoint(request=req2)
    gen1 = resp1.body_iterator
    gen2 = resp2.body_iterator

    await gen1.__anext__()
    await gen2.__anext__()
    assert cam.started == 1

    req1.disconnect = True
    with pytest.raises(StopAsyncIteration):
        await gen1.__anext__()
    assert cam.stopped == 0
    assert cam.cleaned == 0
    assert app_instance.camera_controller is cam

    req2.disconnect = True
    with pytest.raises(StopAsyncIteration):
        await gen2.__anext__()
    assert cam.stopped == 1
    assert cam.cleaned == 1
    assert app_instance.camera_controller is None
    assert calls == [True, False]


@pytest.mark.asyncio
async def test_video_feed_generator_failure(monkeypatch):
    import importlib
    import sys

    fake_alert_mod = types.ModuleType("alert_element_new")
    fake_alert_mod.create_compact_alert_widget = lambda *a, **k: None
    fake_alert_mod.create_demo_configurations = lambda *a, **k: []
    fake_alert_mod.create_email_alert_status_display = lambda *a, **k: None
    fake_alert_mod.create_email_alert_wizard = lambda *a, **k: None
    fake_alert_mod.load_alert_configs = lambda *a, **k: []
    fake_alert_mod.save_alert_configs = lambda *a, **k: None

    class EmailAlertStatusDisplay:
        def __init__(self, *a, **k) -> None:
            self.update_callback = None

    fake_alert_mod.EmailAlertStatusDisplay = EmailAlertStatusDisplay
    sys.modules["cvd.gui.alt_gui_elements.alert_element_new"] = fake_alert_mod

    SimpleGUIApplication = importlib.import_module(
        "cvd.gui.alt_application"
    ).SimpleGUIApplication

    monkeypatch.setattr(
        "cvd.gui.alt_application.load_alert_configs", lambda *a, **k: []
    )
    monkeypatch.setattr(
        "cvd.gui.alt_application.create_demo_configurations", lambda: []
    )
    monkeypatch.setattr(
        "cvd.gui.alt_application.EmailAlertStatusDisplay",
        lambda *a, **k: types.SimpleNamespace(update_callback=None),
    )

    def failing_generate(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "cvd.gui.alt_application.generate_mjpeg_stream", failing_generate
    )

    errors = []
    monkeypatch.setattr(
        "cvd.gui.alt_application.error", lambda *a, **k: errors.append(a)
    )

    app_instance = SimpleGUIApplication(
        controller_manager=DummyControllerManager(),
        config_service=DummyConfigService(),
    )
    with Client.auto_index_client:
        app_instance.register_components()

    route = [r for r in app.routes if getattr(r, "path", None) == "/video_feed"][0]
    endpoint = route.endpoint.__wrapped__

    class DummyRequest:
        async def is_disconnected(self):
            return False

    resp = await endpoint(request=DummyRequest())
    assert resp.status_code == 500
    assert resp.media_type == "application/json"
    assert app_instance._video_feed_connections == 0
    assert errors
