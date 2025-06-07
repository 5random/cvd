import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'program'))

from src.data_handler.sources.sensors import arduino_tc_sensor
from src.data_handler.interface.sensor_interface import SensorConfig

# Disable logging during tests
arduino_tc_sensor.info = lambda *a, **k: None
arduino_tc_sensor.warning = lambda *a, **k: None
arduino_tc_sensor.error = lambda *a, **k: None
arduino_tc_sensor.debug = lambda *a, **k: None
ArduinoTCSensor = arduino_tc_sensor.ArduinoTCSensor
MockArduinoTCBoardSerial = arduino_tc_sensor.MockArduinoTCBoardSerial

@pytest.mark.asyncio
async def test_initialize_uses_mock_serial():
    config = SensorConfig(sensor_id="a1", sensor_type="arduino_tc_board")
    # Force use of mock hardware
    arduino_tc_sensor.ArduinoTCBoardSerial = MockArduinoTCBoardSerial
    arduino_tc_sensor.find_arduino_port = lambda: "COM3"
    sensor = ArduinoTCSensor(config)
    success = await sensor.initialize()
    assert success is True
    assert sensor.is_connected
    assert isinstance(sensor._connection, MockArduinoTCBoardSerial)
    await sensor.cleanup()
