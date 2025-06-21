import json
import types
import pytest
from nicegui import ui

from src.utils.config_service import ConfigurationService
from program.src.gui.gui_elements import gui_sensor_setup_wizard_element as wizard_mod
from program.src.gui.gui_elements.gui_sensor_setup_wizard_element import (
    SensorSetupWizardComponent,
)


class DummySensorManager:
    pass


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
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def clear(self):
            return None

        def classes(self, *a, **k):
            return self

        def props(self, *a, **k):
            return self

        def bind_value_to(self, *a, **k):
            return self

    def dummy_element(*a, **k):
        return Dummy()

    stack_backup = list(ui.context.slot_stack)

    for name in ["column", "row", "label", "input", "number"]:
        monkeypatch.setattr(ui, name, dummy_element)

    if not stack_backup:
        ui.column()
        stack_backup = list(ui.context.slot_stack)

    selects = []

    def dummy_select(options, *a, **k):
        obj = Dummy()
        obj.options = options
        selects.append(obj)
        return obj

    monkeypatch.setattr(ui, "select", dummy_select)

    try:
        yield selects
    finally:
        slot_stack = ui.context.slot_stack
        slot_stack.clear()
        if stack_backup:
            slot_stack.extend(stack_backup)
        else:
            from nicegui import Client

            slot_stack.append(Client.auto_index_client.layout.default_slot)


def test_port_dropdown_populated(monkeypatch, tmp_path, dummy_ui):
    ports = [types.SimpleNamespace(device="COM1"), types.SimpleNamespace(device="COM2")]
    monkeypatch.setattr(wizard_mod.list_ports, "comports", lambda: ports)

    service = create_service(tmp_path)
    wizard = SensorSetupWizardComponent(service, DummySensorManager())
    wizard._render_step2()

    port_names = [p.device for p in ports]
    assert any(sel.options == port_names for sel in dummy_ui)
