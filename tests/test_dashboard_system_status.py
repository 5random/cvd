import json
import pytest

from nicegui import ui

from src.utils.config_service import ConfigurationService
from program.src.gui.gui_tab_components.gui_tab_dashboard_component import DashboardComponent
from program.src.controllers.controller_base import ControllerStatus


def create_service(tmp_path, cfg=None):
    cfg = cfg or {}
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


@pytest.fixture
def dummy_ui(monkeypatch):
    class DummyTimer:
        def cancel(self):
            pass

    class Dummy:
        def classes(self, *args, **kwargs):
            return self
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            pass

    # ensure NiceGUI context exists and preserve stack
    stack_backup = list(ui.context.slot_stack)
    if not stack_backup:
        ui.column()
        stack_backup = list(ui.context.slot_stack)

    dummy = Dummy()
    monkeypatch.setattr(ui, "card", lambda *a, **k: dummy)
    monkeypatch.setattr(ui, "column", lambda *a, **k: dummy)
    monkeypatch.setattr(ui, "label", lambda *a, **k: dummy)
    monkeypatch.setattr(ui, "timer", lambda *a, **k: DummyTimer())
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


class DummySensorManager:
    def get_active_sensors(self):
        return ["s1"]


class DummyController:
    status = ControllerStatus.RUNNING


class DummyControllerManager:
    def list_controllers(self):
        return ["c1"]

    def get_controller(self, cid):
        return DummyController()


def test_render_system_status_with_no_managers(tmp_path, dummy_ui):
    service = create_service(tmp_path)
    dashboard = DashboardComponent(service, None, None)
    dashboard._render_system_status()


def test_render_system_status_no_sensor_manager(tmp_path, dummy_ui):
    service = create_service(tmp_path)
    dashboard = DashboardComponent(service, None, DummyControllerManager())
    dashboard._render_system_status()


def test_render_system_status_no_controller_manager(tmp_path, dummy_ui):
    service = create_service(tmp_path)
    dashboard = DashboardComponent(service, DummySensorManager(), None)
    dashboard._render_system_status()
