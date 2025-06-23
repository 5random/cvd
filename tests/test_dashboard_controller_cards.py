import json
import pytest
from nicegui import ui

from cvd.utils.config_service import ConfigurationService
from cvd.gui.gui_tab_components.gui_tab_dashboard_component import DashboardComponent


def create_service(tmp_path, cfg=None):
    cfg = cfg or {}
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


@pytest.fixture
def dummy_ui(monkeypatch):
    class Dummy:
        def classes(self, *args, **kwargs):
            return self
        def props(self, *args, **kwargs):
            return self
        def on(self, *args, **kwargs):
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
    monkeypatch.setattr(ui, "card", lambda *a, **k: dummy)
    monkeypatch.setattr(ui, "column", lambda *a, **k: dummy)
    monkeypatch.setattr(ui, "label", lambda *a, **k: dummy)
    monkeypatch.setattr(ui, "row", lambda *a, **k: dummy)
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


def test_refresh_controllers_no_manager(tmp_path, dummy_ui):
    cfg = {
        "controllers": [
            {
                "c1": {
                    "name": "c1",
                    "type": "motion_detection",
                    "interface": "usb_camera",
                    "device_index": 0,
                    "show_on_dashboard": True,
                    "enabled": True,
                    "parameters": {"device_index": 0},
                }
            }
        ]
    }
    service = create_service(tmp_path, cfg)
    dashboard = DashboardComponent(service, None, None)
    dashboard.refresh_controllers()
    assert dashboard._controller_cards == {}
