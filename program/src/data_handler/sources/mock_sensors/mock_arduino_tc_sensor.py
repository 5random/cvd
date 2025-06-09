from __future__ import annotations
import asyncio
from src.data_handler.sources.sensors.arduino_tc_sensor import ArduinoTCSensor
from src.data_handler.sources.mock_hardware.arduino_tc_board import (
    MockArduinoTCBoardSerial,
    mock_find_arduino_port,
)
from src.utils.log_utils.log_service import info, error


class MockArduinoTCSensor(ArduinoTCSensor):
    """Arduino TC Board sensor using mock hardware."""

    async def initialize(self) -> bool:
        try:
            self._port = self._config.parameters.get("port")
            if not self._port:
                loop = asyncio.get_running_loop()
                self._port = await loop.run_in_executor(
                    self._executor, mock_find_arduino_port
                )

            baudrate = self._config.parameters.get("baudrate", 9600)
            timeout = self._config.parameters.get("timeout", 2.0)
            self._connection = MockArduinoTCBoardSerial(
                port=self._port,
                baudrate=baudrate,
                timeout=timeout,
            )
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._connection.connect)

            # Configure sensors after connecting
            sensor_index = self._config.parameters.get("channel", 0)
            await loop.run_in_executor(
                self._executor,
                lambda: self._connection.configure_sensors([sensor_index]),
            )

            self._is_connected = True
            info(
                f"Mock Arduino TC sensor {self.sensor_id} initialized on port {self._port}"
            )
            return True
        except Exception as e:
            error(f"Failed to initialize mock Arduino TC sensor {self.sensor_id}: {e}")
            self._is_connected = False
            return False
