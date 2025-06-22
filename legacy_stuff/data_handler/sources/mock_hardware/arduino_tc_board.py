from __future__ import annotations
import random
from typing import Optional
from src.utils.log_service import info, debug


class MockArduinoTCBoardSerial:
    """Mock Arduino TC Board for testing when hardware is not available."""

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connected = False
        self._configured_indices = []

    def connect(self) -> None:
        self.connected = True
        info(f"Mock Arduino connected on {self.port}")

    def disconnect(self) -> None:
        self.connected = False
        info(f"Mock Arduino disconnected on {self.port}")

    def configure_sensors(self, indices: list[int]) -> str:
        """Store configured sensor indices and return success."""
        self._configured_indices = list(indices)
        debug(f"Mock configure_sensors: {self._configured_indices}")
        return "OK"

    def read_temperature(self, sensor_index: int) -> float:
        if sensor_index not in self._configured_indices:
            raise ValueError(f"Sensor index {sensor_index} not configured")
        temp = random.uniform(20.0, 30.0)
        debug(f"Mock read_temperature on sensor {sensor_index}: {temp}")
        return temp


def mock_find_arduino_port() -> Optional[str]:
    """Mock port finding function."""
    return "COM3"
