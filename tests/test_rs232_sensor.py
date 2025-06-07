import asyncio
import sys
from pathlib import Path
import pytest

# Ensure src package is importable
sys.path.append(str(Path(__file__).resolve().parents[1] / "program"))

from src.data_handler.sources.sensors import rs232_sensor
from src.data_handler.sources.sensors.rs232_sensor import RS232Sensor, MockRS232Serial
from src.data_handler.interface.sensor_interface import SensorConfig, SensorStatus


class InvalidMockSerial(MockRS232Serial):
    """Mock serial port that returns invalid data."""

    def readline(self) -> bytes:  # override to return invalid data
        return b"invalid-data\n"


@pytest.mark.asyncio
async def test_rs232sensor_read_invalid_data(monkeypatch):
    """Reading invalid data should return a SensorStatus.ERROR result."""

    # Suppress log service usage
    monkeypatch.setattr(rs232_sensor, "info", lambda *a, **k: None)
    monkeypatch.setattr(rs232_sensor, "warning", lambda *a, **k: None)
    monkeypatch.setattr(rs232_sensor, "error", lambda *a, **k: None)
    monkeypatch.setattr(rs232_sensor, "debug", lambda *a, **k: None)

    cfg = SensorConfig(sensor_id="sen1", sensor_type="rs232")
    sensor = RS232Sensor(cfg)
    sensor._connection = InvalidMockSerial(port="COM1")
    sensor._connection.open()
    sensor._is_connected = True

    reading = await sensor.read()
    assert reading.status == SensorStatus.ERROR
    assert reading.error_message is not None
