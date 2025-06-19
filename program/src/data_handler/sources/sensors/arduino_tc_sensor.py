"""Arduino TC Board sensor implementation using :class:`BaseSensor`."""

import asyncio
import time
from typing import Dict, Any, Optional
from concurrent.futures import Executor
from src.data_handler.interface.sensor_interface import (
    SensorReading,
    SensorStatus,
    SensorConfig,
)
from .base_sensor import BaseSensor
from program.src.utils.log_service import info, warning, error, debug
from src.data_handler.sources.mock_hardware import (
    MockArduinoTCBoardSerial,
    mock_find_arduino_port,
)

# Try to import real Arduino library, fall back to mock
try:
    from arduino.control_arduino_tc_board import ArduinoTCBoardSerial, find_arduino_port

    info("Using real Arduino TC Board library")
except ImportError:
    warning("Arduino library not available, using mock implementation")
    ArduinoTCBoardSerial = MockArduinoTCBoardSerial
    find_arduino_port = mock_find_arduino_port


class ArduinoTCSensor(BaseSensor):
    """Arduino TC Board sensor implementation"""

    def __init__(self, config: SensorConfig, executor: Optional[Executor] = None):
        super().__init__(config, executor)
        self._port: Optional[str] = None

    @property
    def sensor_type(self) -> str:
        return "arduino_tc_board"

    async def initialize(self) -> bool:
        """Initialize Arduino TC Board connection"""
        try:
            # Get port from config or auto-detect
            self._port = self._config.parameters.get("port")
            if not self._port:
                loop = asyncio.get_running_loop()
                self._port = await loop.run_in_executor(
                    self._executor, find_arduino_port
                )

            if not self._port:
                warning(f"No Arduino port found for sensor {self.sensor_id}")
                return False

            # Initialize connection
            baudrate = self._config.parameters.get("baudrate", 9600)
            timeout = self._config.parameters.get("timeout", 2.0)
            self._connection = ArduinoTCBoardSerial(
                port=self._port, baudrate=baudrate, timeout=timeout
            )

            # Connect in thread to avoid blocking
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._connection.connect)

            # Configure sensor index after connecting
            sensor_index = self._config.parameters.get("channel", 0)
            await loop.run_in_executor(
                self._executor,
                lambda: self._connection.configure_sensors([sensor_index]),
            )

            self._is_connected = True

            info(f"Arduino TC sensor {self.sensor_id} initialized on port {self._port}")
            return True
        except Exception as e:
            error(f"Failed to initialize Arduino TC sensor {self.sensor_id}: {e}")
            self._is_connected = False
            return False

    async def read(self) -> SensorReading:
        """Read temperature from Arduino TC Board"""
        if not self.is_connected or self._connection is None:
            return SensorReading.create_offline(self.sensor_id)

        try:
            # Use sensor_index instead of channel to match real Arduino interface
            sensor_index = self._config.parameters.get("channel", 0)

            def read_temp():
                if self._connection is not None:
                    return self._connection.read_temperature(sensor_index)
                return None

            # Read temperature in background thread
            loop = asyncio.get_running_loop()
            temperature = await loop.run_in_executor(self._executor, read_temp)

            if temperature is not None:
                return SensorReading(
                    sensor_id=self.sensor_id,
                    value=temperature,
                    timestamp=time.time(),
                    status=SensorStatus.OK,
                    metadata={
                        "sensor_index": sensor_index,
                        "port": self._port,
                        "sensor_type": self.sensor_type,
                    },
                )
            else:
                return SensorReading.create_error(
                    self.sensor_id, "No temperature reading received"
                )
        except Exception as e:
            error(f"Error reading from Arduino TC sensor {self.sensor_id}: {e}")
            return SensorReading.create_error(self.sensor_id, str(e))

    async def configure(self, config: Dict[str, Any]) -> None:
        """Apply configuration to sensor"""
        # Update internal config
        self._config.parameters.update(config)

        # If connection parameters changed, reinitialize
        if any(key in config for key in ["port", "baudrate", "timeout"]):
            await self.cleanup()
            await self.initialize()

        info(f"Arduino TC sensor {self.sensor_id} reconfigured")

    async def cleanup(self) -> None:
        """Clean shutdown of Arduino TC Board connection"""
        if self._connection:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(self._executor, self._connection.disconnect)
                info(f"Arduino TC sensor {self.sensor_id} disconnected")
            except Exception as e:
                error(f"Error disconnecting Arduino TC sensor {self.sensor_id}: {e}")
            finally:
                self._connection = None
                self._is_connected = False
