import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "program"))

from src.data_handler.sources.sensors import rs232_sensor
from src.data_handler.interface.sensor_interface import SensorConfig, SensorStatus

# Patch logging functions to avoid configuration requirements
rs232_sensor.info = lambda *a, **k: None
rs232_sensor.warning = lambda *a, **k: None
rs232_sensor.error = lambda *a, **k: None
rs232_sensor.debug = lambda *a, **k: None

RS232Sensor = rs232_sensor.RS232Sensor

class BadSerial:
    def readline(self):
        return b"INVALID\n"

@pytest.mark.asyncio
async def test_read_returns_error_on_invalid_data():
    config = SensorConfig(sensor_id="test", sensor_type="rs232")
    sensor = RS232Sensor(config)
    sensor._connection = BadSerial()
    sensor._is_connected = True
    reading = await sensor.read()
    assert reading.status == SensorStatus.ERROR
    assert reading.value is None

