"""Mock hardware interfaces used for tests and development.

This module exposes small mock classes that emulate serial devices so that the
data handler can run without real hardware connected.
"""

from .rs232 import MockRS232Serial
from .arduino_tc_board import MockArduinoTCBoardSerial, mock_find_arduino_port

__all__ = [
    "MockRS232Serial",
    "MockArduinoTCBoardSerial",
    "mock_find_arduino_port",
]
