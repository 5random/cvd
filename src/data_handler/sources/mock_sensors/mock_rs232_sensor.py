from __future__ import annotations

from src.data_handler.sources.sensors.rs232_sensor import RS232Sensor
from src.data_handler.sources.mock_hardware.rs232 import MockRS232Serial
from src.utils.log_service import info, error

class MockRS232Sensor(RS232Sensor):
    """RS232 sensor that always uses the mock serial connection."""

    async def initialize(self) -> bool:
        try:
            self._port = self._config.parameters.get("port", "COM1")
            baudrate = self._config.parameters.get("baudrate", 9600)
            timeout = self._config.parameters.get("timeout", 1.0)

            self._connection = MockRS232Serial(
                port=self._port,
                baudrate=baudrate,
                timeout=timeout,
            )
            if hasattr(self._connection, "open") and not getattr(self._connection, "is_open", False):
                self._connection.open()
            self._is_connected = True
            info(f"Mock RS232 sensor {self.sensor_id} initialized on port {self._port}")
            return True
        except Exception as e:
            error(f"Failed to initialize mock RS232 sensor {self.sensor_id}: {e}")
            self._is_connected = False
            return False
