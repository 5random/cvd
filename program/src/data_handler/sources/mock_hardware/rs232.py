from __future__ import annotations
import random
from src.utils.log_utils.log_service import info

class MockRS232Serial:
    """Mock RS232 for testing when hardware is not available."""

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = False

    def open(self) -> None:
        self.is_open = True
        info(f"Mock RS232 opened on {self.port}")

    def close(self) -> None:
        self.is_open = False
        info(f"Mock RS232 closed on {self.port}")

    def readline(self) -> bytes:
        if not self.is_open:
            raise RuntimeError("Serial port not open")
        value = random.uniform(0.0, 100.0)
        return f"{value:.2f}\n".encode("utf-8")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
