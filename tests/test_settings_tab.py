import json
import pytest
from nicegui import ui

from src.gui.application import WebApplication
from src.utils.config_service import ConfigurationService


class DummySensorManager:
    pass


class DummyNotificationCenter:
    def create_notification_button(self):
        pass


class DummyControllerManager:
    pass


def create_service(tmp_path):
    cfg = {"ui": {"title": "Initial", "refresh_rate_ms": 1000}}
    default = {"ui": {"title": "Default", "refresh_rate_ms": 500}}
    cfg_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    cfg_path.write_text(json.dumps(cfg))
    default_path.write_text(json.dumps(default))
    return ConfigurationService(cfg_path, default_path), cfg_path


@pytest.fixture
def dummy_ui(monkeypatch):
    created = []

    class Dummy:
        def __init__(self, label=None, value=None):
            self.label = label
            self.value = value

        def classes(self, *a, **k):
            return self

        def props(self, *a, **k):
            return self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    def element(*a, **k):
        return Dummy()

    def input_element(*a, **k):
        obj = Dummy(label=k.get("label"), value=k.get("value"))
        created.append(obj)
        return obj

    stack_backup = list(ui.context.slot_stack)
    if not stack_backup:
        from nicegui import Client

        stack_backup = [Client.auto_index_client.layout.default_slot]
        ui.context.slot_stack.extend(stack_backup)

    for name in ["row", "card", "label", "button"]:
        monkeypatch.setattr(ui, name, element)
    monkeypatch.setattr(ui, "input", input_element)
    monkeypatch.setattr(ui, "number", input_element)
    monkeypatch.setattr(ui, "notify", lambda *a, **k: None)

    try:
        yield created
    finally:
        slot_stack = ui.context.slot_stack
        slot_stack.clear()
        slot_stack.extend(stack_backup)


def create_app(service, monkeypatch):
    monkeypatch.setattr(
        "src.gui.application.create_notification_center",
        lambda *a, **k: DummyNotificationCenter(),
    )
    monkeypatch.setattr(
        "src.gui.application.create_cvd_controller_manager",
        lambda: DummyControllerManager(),
    )
    return WebApplication(service, DummySensorManager())


def test_settings_inputs_rendered(tmp_path, monkeypatch, dummy_ui):
    service, _ = create_service(tmp_path)
    app = create_app(service, monkeypatch)
    app._create_settings_content()
    labels = [i.label for i in dummy_ui]
    assert "System Title" in labels
    assert "Refresh Rate (ms)" in labels


def test_save_settings_updates_config(tmp_path, monkeypatch, dummy_ui):
    service, cfg_path = create_service(tmp_path)
    app = create_app(service, monkeypatch)
    app._create_settings_content()
    app._title_input.value = "Updated"
    app._refresh_rate_input.value = 2500
    app._save_settings()
    service.reload()
    assert service.get("ui.title", str) == "Updated"
    assert service.get("ui.refresh_rate_ms", int) == 2500
    data = json.loads(cfg_path.read_text())
    assert data["ui"]["title"] == "Updated"
    assert data["ui"]["refresh_rate_ms"] == 2500


def test_reset_settings_restores_defaults(tmp_path, monkeypatch, dummy_ui):
    service, cfg_path = create_service(tmp_path)
    app = create_app(service, monkeypatch)
    app._create_settings_content()
    app._title_input.value = "Changed"
    app._refresh_rate_input.value = 2000
    app._save_settings()
    app._reset_configuration()
    service.reload()
    assert service.get("ui.title", str) == "Default"
    assert service.get("ui.refresh_rate_ms", int) == 500
    data = json.loads(cfg_path.read_text())
    assert data["ui"]["title"] == "Default"
    assert data["ui"]["refresh_rate_ms"] == 500
    assert app._title_input.value == "Default"
    assert app._refresh_rate_input.value == 500
