from __future__ import annotations
import random
from typing import Optional
from src.utils.log_utils.log_service import info, debug

class MockArduinoTCBoardSerial:
    """Mock Arduino TC Board for testing when hardware is not available."""

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connected = False

    def connect(self) -> None:
        self.connected = True
        info(f"Mock Arduino connected on {self.port}")

    def disconnect(self) -> None:
        self.connected = False
        info(f"Mock Arduino disconnected on {self.port}")

    def read_temperature(self, sensor_index: int) -> float:
        temp = random.uniform(20.0, 30.0)
        debug(f"Mock read_temperature on sensor {sensor_index}: {temp}")
        return temp


def mock_find_arduino_port() -> Optional[str]:
    """Mock port finding function."""
    return "COM3"
