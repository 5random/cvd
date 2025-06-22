from abc import ABC, abstractmethod
from typing import Optional
from concurrent.futures import Executor

from src.data_handler.interface.sensor_interface import SensorInterface, SensorConfig


class BaseSensor(SensorInterface, ABC):
    """Base class for sensors providing connection handling and configuration."""

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

    @property
    @abstractmethod
    def sensor_type(self) -> str:
        """Type identifier for the concrete sensor implementation."""
        pass
