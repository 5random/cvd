import pytest

from program.src.data_handler.sources.sensors import arduino_tc_sensor
from program.src.data_handler.sources.mock_hardware.arduino_tc_board import (
    MockArduinoTCBoardSerial,
)
from program.src.data_handler.interface.sensor_interface import SensorConfig

# Disable logging during tests
arduino_tc_sensor.info = lambda *a, **k: None
arduino_tc_sensor.warning = lambda *a, **k: None
arduino_tc_sensor.error = lambda *a, **k: None
arduino_tc_sensor.debug = lambda *a, **k: None
ArduinoTCSensor = arduino_tc_sensor.ArduinoTCSensor


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


@pytest.mark.asyncio
async def test_initialize_configures_channel(monkeypatch):
    class SpySerial(MockArduinoTCBoardSerial):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.configure_calls = []

        def configure_sensors(self, indices):
            self.configure_calls.append(indices)
            return super().configure_sensors(indices)

    # Force use of spy serial
    monkeypatch.setattr(arduino_tc_sensor, "ArduinoTCBoardSerial", SpySerial)
    monkeypatch.setattr(arduino_tc_sensor, "find_arduino_port", lambda: "COM3")

    config = SensorConfig(
        sensor_id="a2", sensor_type="arduino_tc_board", parameters={"channel": 2}
    )
    sensor = ArduinoTCSensor(config)
    success = await sensor.initialize()
    assert success is True
    assert isinstance(sensor._connection, SpySerial)
    assert sensor._connection.configure_calls == [[2]]
    await sensor.cleanup()
