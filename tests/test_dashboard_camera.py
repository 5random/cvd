import json
import pytest
from nicegui import ui

from src.utils.config_service import ConfigurationService
from src.gui.gui_tab_components.gui_tab_dashboard_component import DashboardComponent


def create_service(tmp_path, cfg):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


def test_motion_detection_camera_detection(tmp_path):
    cfg = {
        "controllers": [
            {
                "md1": {
                    "name": "MD",
                    "type": "motion_detection",
                    "parameters": {"cam_id": "cam1"},
                    "show_on_dashboard": True,
                    "enabled": True,
                }
            }
        ]
    }

    service = create_service(tmp_path, cfg)
    dashboard = DashboardComponent(service, None, None)

    assert dashboard._should_show_camera() is True
    assert dashboard._get_camera_controllers() == ["md1"]


def test_multiple_cameras(tmp_path):
    cfg = {
        "controllers": [
            {
                "cam1": {
                    "name": "C1",
                    "type": "motion_detection",
                    "show_on_dashboard": True,
                    "enabled": True,
                    "parameters": {"device_index": 0},
                }
            },
            {
                "cam2": {
                    "name": "C2",
                    "type": "motion_detection",
                    "show_on_dashboard": True,
                    "enabled": True,
                    "parameters": {"device_index": 1},
                }
            },
        ]
    }

    service = create_service(tmp_path, cfg)
    dashboard = DashboardComponent(service, None, None)

    cams = dashboard._get_camera_controllers()
    assert set(cams) == {"cam1", "cam2"}


@pytest.fixture
def dummy_ui(monkeypatch):
    class Dummy:
        def __init__(self, *a, **k):
            pass

        def classes(self, *a, **k):
            return self

        def props(self, *a, **k):
            return self

        def on(self, *a, **k):
            return self

        def clear(self):
            return self

        def delete(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    stack_backup = list(ui.context.slot_stack)
    if not stack_backup:
        ui.column()
        stack_backup = list(ui.context.slot_stack)

    dummy = Dummy()
    for name in [
        "card",
        "column",
        "label",
        "row",
        "select",
        "checkbox",
        "icon",
    ]:
        monkeypatch.setattr(ui, name, lambda *a, **k: dummy)

    try:
        yield dummy
    finally:
        slot_stack = ui.context.slot_stack
        slot_stack.clear()
        if stack_backup:
            slot_stack.extend(stack_backup)
        else:
            from nicegui import Client

            slot_stack.append(Client.auto_index_client.layout.default_slot)


class DummyStream:
    def __init__(self, *a, **k):
        self.kwargs = k

    def render(self):
        pass


def test_render_camera_stream_invalid_resolution(tmp_path, monkeypatch, dummy_ui):
    cfg = {
        "controllers": [
            {
                "cam1": {
                    "name": "C1",
                    "type": "motion_detection",
                    "show_on_dashboard": True,
                    "enabled": True,
                    "parameters": {"cam_id": "cam1"},
                    "settings": {"resolution": "bad"},
                }
            }
        ]
    }
    service = create_service(tmp_path, cfg)
    dashboard = DashboardComponent(service, None, None)
    monkeypatch.setattr(
        "src.gui.gui_tab_components.gui_tab_dashboard_component.CameraStreamComponent",
        DummyStream,
    )
    dashboard._render_camera_stream()
    assert DummyStream.kwargs.get("controller_id") == "cam1"


def test_render_camera_stream_string_resolution(tmp_path, monkeypatch, dummy_ui):
    cfg = {
        "controllers": [
            {
                "cam1": {
                    "name": "C1",
                    "type": "motion_detection",
                    "show_on_dashboard": True,
                    "enabled": True,
                    "parameters": {"cam_id": "cam1"},
                    "settings": {"resolution": "640x480"},
                }
            }
        ]
    }
    service = create_service(tmp_path, cfg)
    dashboard = DashboardComponent(service, None, None)
    streams = []

    class RecStream(DummyStream):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            streams.append((k.get("max_width"), k.get("max_height")))

    monkeypatch.setattr(
        "src.gui.gui_tab_components.gui_tab_dashboard_component.CameraStreamComponent",
        RecStream,
    )
    dashboard._render_camera_stream()
    assert RecStream.kwargs.get("controller_id") == "cam1"
    assert streams and streams[0] == (640, 480)

