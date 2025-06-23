import pytest

from cvd.legacy_sensors import rs232_sensor
from cvd.legacy_sensors.rs232_sensor import RS232Sensor
from cvd.data_handler.sources.mock_hardware.rs232 import MockRS232Serial
from cvd.data_handler.interface.sensor_interface import SensorConfig, SensorStatus


class InvalidMockSerial(MockRS232Serial):

    def readline(self) -> bytes:
        return b"invalid-data\n"


class BadSerial:
    def readline(self):
        return b"INVALID\n"


@pytest.mark.asyncio
async def test_rs232sensor_read_invalid_data(monkeypatch):
    for name in ["info", "warning", "error", "debug"]:
        monkeypatch.setattr(rs232_sensor, name, lambda *a, **k: None, raising=False)

    cfg = SensorConfig(sensor_id="sen1", sensor_type="rs232")
    sensor = RS232Sensor(cfg)
    sensor._connection = InvalidMockSerial(port="COM1")
    sensor._connection.open()
    sensor._is_connected = True

    reading = await sensor.read()
    assert reading.status == SensorStatus.ERROR
    assert reading.error_message is not None


@pytest.mark.asyncio
async def test_read_returns_error_on_invalid_data():
    rs232_sensor.info = lambda *a, **k: None
    rs232_sensor.warning = lambda *a, **k: None
    rs232_sensor.error = lambda *a, **k: None
    rs232_sensor.debug = lambda *a, **k: None

    config = SensorConfig(sensor_id="test", sensor_type="rs232")
    sensor = RS232Sensor(config)
    sensor._connection = BadSerial()
    sensor._is_connected = True
    reading = await sensor.read()
    assert reading.status == SensorStatus.ERROR
    assert reading.value is None
