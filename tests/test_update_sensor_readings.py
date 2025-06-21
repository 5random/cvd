import json
import time
from typing import Dict

import pytest
from nicegui import ui

from program.src.gui.application import WebApplication
from program.src.data_handler.interface.sensor_interface import SensorReading, SensorStatus
from src.utils.config_service import ConfigurationService


class DummySensorManager:
    def __init__(self, readings: Dict[str, SensorReading]):
        self._readings = readings

    def get_latest_readings(self) -> Dict[str, SensorReading]:
        return self._readings


@pytest.fixture
def dummy_ui(monkeypatch):
    captured = []

    class Dummy:
        def __init__(self, text=None):
            if text is not None:
                captured.append(text)

        def classes(self, *args, **kwargs):
            return self

        def props(self, *args, **kwargs):
            return self

        def clear(self):
            captured.clear()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    stack_backup = list(ui.context.slot_stack)
    if not stack_backup:
        ui.column()
        stack_backup = list(ui.context.slot_stack)

    monkeypatch.setattr(ui, "row", lambda *a, **k: Dummy())
    monkeypatch.setattr(ui, "label", lambda text=None, *a, **k: Dummy(text))

    try:
        yield Dummy, captured
    finally:
        slot_stack = ui.context.slot_stack
        slot_stack.clear()
        if stack_backup:
            slot_stack.extend(stack_backup)
        else:
            from nicegui import Client

            slot_stack.append(Client.auto_index_client.layout.default_slot)


def test_update_sensor_readings_units(tmp_path, dummy_ui):
    Dummy, captured = dummy_ui

    cfg = {
        "sensors": [
            {
                "s1": {
                    "name": "s1",
                    "type": "temperature",
                    "source": "mock",
                    "interface": "serial",
                    "port": "COM1",
                    "channel": 1,
                    "unit": "K",
                    "enabled": True,
                }
            },
            {
                "s2": {
                    "name": "s2",
                    "type": "temperature",
                    "source": "mock",
                    "interface": "serial",
                    "port": "COM1",
                    "channel": 1,
                    "unit": "mV",
                    "enabled": True,
                }
            },
            {
                "s3": {
                    "name": "s3",
                    "type": "temperature",
                    "source": "mock",
                    "interface": "serial",
                    "port": "COM1",
                    "channel": 1,
                    "enabled": True,
                }
            },
        ]
    }
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    readings = {
        "s1": SensorReading(
            "s1", 1.0, time.time(), SensorStatus.OK, metadata={"unit": "F"}
        ),
        "s2": SensorReading("s2", 2.0, time.time(), SensorStatus.OK, metadata={}),
        "s3": SensorReading("s3", 3.0, time.time(), SensorStatus.OK, metadata={}),
    }
    manager = DummySensorManager(readings)

    app = WebApplication(service, manager)
    app._sensor_readings_container = Dummy()

    app._update_sensor_readings()

    assert captured == [
        "s1",
        "1.00F",
        "s2",
        "2.00mV",
        "s3",
        "3.00°C",
    ]
