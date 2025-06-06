"""
RS232 sensor implementation using the SensorInterface.
"""
import asyncio
import time
import random
from typing import Dict, Any, Optional
from concurrent.futures import Executor
import serial
from src.data_handler.interface.sensor_interface import SensorInterface, SensorReading, SensorStatus, SensorConfig
from src.utils.log_utils.log_service import info, warning, error, debug

class MockRS232Serial:
    """Mock RS232 for testing when hardware is not available"""

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = False

    def open(self) -> None:
        """Mock open"""
        self.is_open = True
        info(f"Mock RS232 opened on {self.port}")

    def close(self) -> None:
        """Mock close"""
        self.is_open = False
        info(f"Mock RS232 closed on {self.port}")

    def readline(self) -> bytes:
        """Mock readline - returns random sensor data"""
        if not self.is_open:
            raise RuntimeError("Serial port not open")
        
        # Simulate random sensor reading
        value = random.uniform(0.0, 100.0)
        return f"{value:.2f}\n".encode('utf-8')

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class RS232Sensor(SensorInterface):
    """RS232 sensor implementation"""

    def __init__(self, config: SensorConfig, executor: Optional[Executor] = None):
        self._config = config
        self._connection = None
        self._is_connected = False
        self._port: str = ""
        self._executor = executor

    @property
    def sensor_id(self) -> str:
        return self._config.sensor_id

    @property
    def sensor_type(self) -> str:
        return "rs232"

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self._connection is not None

    async def initialize(self) -> bool:
        """Initialize RS232 connection"""
        try:
            # Get connection parameters from config
            self._port = self._config.parameters.get('port', 'COM1')
            baudrate = self._config.parameters.get('baudrate', 9600)
            timeout = self._config.parameters.get('timeout', 1.0)

            try:
                # Try to connect to real serial port
                self._connection = serial.Serial(
                    port=self._port,
                    baudrate=baudrate,
                    timeout=timeout
                )
                info(f"Real RS232 connection established on {self._port}")
            except Exception as e:
                # Fall back to mock if real hardware not available
                warning(f"Real RS232 not available ({e}), using mock")
                self._connection = MockRS232Serial(
                    port=self._port,
                    baudrate=baudrate,
                    timeout=timeout
                )

            # Test connection
            if hasattr(self._connection, 'open'):
                self._connection.open()
            
            self._is_connected = True
            info(f"RS232 sensor {self.sensor_id} initialized on port {self._port}")
            return True
            
        except Exception as e:
            error(f"Failed to initialize RS232 sensor {self.sensor_id}: {e}")
            self._is_connected = False
            return False

    async def read(self) -> SensorReading:
        """Read data from RS232 port"""
        if not self.is_connected or self._connection is None:
            return SensorReading.create_offline(self.sensor_id)

        try:
            # capture connection in a local var so it’s non-None
            conn = self._connection

            def read_data():
                if conn is None or not hasattr(conn, 'readline'):
                    return None
                line = conn.readline()
                # Convert memoryview or bytes to string
                if isinstance(line, memoryview):
                    line = line.tobytes()
                if isinstance(line, (bytes, bytearray)):
                    line = line.decode('utf-8', errors='ignore')
                elif not isinstance(line, str):
                    return None
                return float(line.strip())

            # Read data in background thread
            loop = asyncio.get_running_loop()
            value = await loop.run_in_executor(self._executor, read_data)

            if value is not None:
                return SensorReading(
                    sensor_id=self.sensor_id,
                    value=value,
                    timestamp=time.time(),
                    status=SensorStatus.OK,
                    metadata={
                        'port': self._port,
                        'sensor_type': self.sensor_type
                    }
                )
            else:
                return SensorReading.create_error(
                    self.sensor_id,
                    "No data received from RS232"
                )
                
        except Exception as e:
            error(f"Error reading from RS232 sensor {self.sensor_id}: {e}")
            return SensorReading.create_error(self.sensor_id, str(e))

    async def configure(self, config: Dict[str, Any]) -> None:
        """Apply configuration to sensor"""
        # Update internal config
        self._config.parameters.update(config)

        # If connection parameters changed, reinitialize
        if any(key in config for key in ['port', 'baudrate', 'timeout']):
            await self.cleanup()
            await self.initialize()

        info(f"RS232 sensor {self.sensor_id} reconfigured")

    async def cleanup(self) -> None:
        """Clean shutdown of RS232 connection"""
        if self._connection:
            try:
                if hasattr(self._connection, 'close'):
                    self._connection.close()
                info(f"RS232 sensor {self.sensor_id} disconnected")
            except Exception as e:
                error(f"Error disconnecting RS232 sensor {self.sensor_id}: {e}")
            finally:
                self._connection = None
                self._is_connected = False
