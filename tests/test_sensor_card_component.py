import pytest
from nicegui import ui

from program.src.gui.gui_tab_components.gui_tab_sensors_component import SensorCardComponent, SensorInfo


class Dummy:
    def __init__(self, text=None, name=None):
        self.text = text
        self.name = name
    def classes(self, *a, **k):
        return self
    def props(self, *a, **k):
        return self
    def set_text(self, text):
        self.text = text
        return self
    def set_name(self, name):
        self.name = name
        return self
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        pass


@pytest.fixture
def dummy_ui(monkeypatch):
    monkeypatch.setattr(ui, "card", lambda *a, **k: Dummy())
    monkeypatch.setattr(ui, "card_section", lambda *a, **k: Dummy())
    monkeypatch.setattr(ui, "row", lambda *a, **k: Dummy())
    monkeypatch.setattr(ui, "column", lambda *a, **k: Dummy())
    monkeypatch.setattr(ui, "icon", lambda *a, **k: Dummy())
    monkeypatch.setattr(ui, "button", lambda *a, **k: Dummy())
    monkeypatch.setattr(ui, "menu", lambda *a, **k: Dummy())
    monkeypatch.setattr(ui, "menu_item", lambda *a, **k: Dummy())
    monkeypatch.setattr(ui, "dialog", lambda *a, **k: Dummy())
    monkeypatch.setattr(ui, "label", lambda text=None, *a, **k: Dummy(text))
    yield


class DummyManager:
    pass


class DummyService:
    pass


def create_info(status: str) -> SensorInfo:
    return SensorInfo(
        sensor_id="s1",
        name="Sensor",
        sensor_type="temperature",
        source="mock",
        interface="serial",
        port="COM1",
        enabled=True,
        connected=True,
        polling=False,
        last_reading=None,
        status=status,
        current_value=None,
        poll_interval_ms=1000,
        config={},
    )


def test_status_label_updates(monkeypatch, dummy_ui):
    info = create_info("offline")
    comp = SensorCardComponent(info, DummyManager(), DummyService())
    comp.render()
    assert comp._status_label.text == "OFFLINE"

    updated = create_info("ok")
    comp.update_sensor_info(updated)
    assert comp._status_label.text == "OK"
