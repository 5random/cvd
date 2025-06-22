"""
Core interfaces and data structures for the CVD Tracker system.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
import time
from src.utils.log_service import info, warning, error, debug

class SensorStatus(Enum):
    """Status enumeration for sensor readings"""
    OK = "ok"
    ERROR = "error"
    OFFLINE = "offline"
    CALIBRATING = "calibrating"
    TIMEOUT = "timeout"

@dataclass
class SensorReading:
    """Data structure for sensor readings"""
    sensor_id: str
    value: Optional[float]
    timestamp: float
    status: SensorStatus = SensorStatus.OK
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create_error(cls, sensor_id: str, error_message: str) -> 'SensorReading':
        """Create an error reading"""
        # use positional args: sensor_id, value, timestamp, status, error_message (metadata defaults)
        return cls(
            sensor_id,
            None,
            time.time(),
            SensorStatus.ERROR,
            error_message
        )
    
    @classmethod
    def create_offline(cls, sensor_id: str) -> 'SensorReading':
        """Create an offline reading"""
        # use positional args: sensor_id, value, timestamp, status (error_message and metadata default)
        return cls(
            sensor_id,
            None,
            time.time(),
            SensorStatus.OFFLINE
        )
    
    def is_valid(self) -> bool:
        """Check if reading contains valid data"""
        return self.status == SensorStatus.OK and self.value is not None

class SensorInterface(ABC):
    """Base interface for all sensor types"""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize sensor connection
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def read(self) -> SensorReading:
        """Read single value from sensor
        
        Returns:
            SensorReading with current sensor data
        """
        pass
    
    @abstractmethod
    async def configure(self, config: Dict[str, Any]) -> None:
        """Apply configuration to sensor
        
        Args:
            config: Configuration dictionary for this sensor
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean shutdown of sensor"""
        pass
    
    @property
    @abstractmethod
    def sensor_id(self) -> str:
        """Unique identifier for this sensor"""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if sensor is connected and ready"""
        pass
    
    @property
    @abstractmethod
    def sensor_type(self) -> str:
        """Type identifier for this sensor (e.g., 'arduino_tc_board', 'rs232')"""
        pass

@dataclass
class SensorConfig:
    """Configuration for a sensor instance"""
    sensor_id: str
    sensor_type: str
    enabled: bool = True
    poll_interval_ms: int = 1000
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def get_poll_interval_seconds(self) -> float:
        """Get polling interval in seconds"""
        return self.poll_interval_ms / 1000.0
