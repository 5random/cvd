from abc import ABC
from typing import Optional
from concurrent.futures import Executor

from src.data_handler.interface.sensor_interface import SensorInterface, SensorConfig


class BaseSensor(SensorInterface, ABC):
    """Common functionality shared by sensor implementations."""

    def __init__(self, config: SensorConfig, executor: Optional[Executor] = None):
        self._config = config
        self._connection = None
        self._is_connected = False
        self._executor = executor

    @property
    def sensor_id(self) -> str:
        """Return the configured sensor id."""
        return self._config.sensor_id

    @property
    def is_connected(self) -> bool:
        """Return True if a connection object exists and the sensor is marked connected."""
        return self._is_connected and self._connection is not None
