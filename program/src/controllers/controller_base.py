"""
Base classes for the controller system following the ProcessingStage pattern.
"""
from typing import Dict, List, Any, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import time

from src.data_handler.interface.sensor_interface import SensorReading
from src.utils.log_utils.log_service import info, warning, error, debug

T = TypeVar('T')

class ControllerType(Enum):
    """Types of controllers"""
    MOTION_DETECTION = "motion_detection"
    STATE_DERIVATION = "state_derivation"
    CUSTOM = "custom"

class ControllerStatus(Enum):
    """Controller status enumeration"""
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"
    PAUSED = "paused"

@dataclass
class ControllerInput:
    """Input data for controllers"""
    sensor_data: Dict[str, SensorReading] = field(default_factory=dict)
    controller_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass 
class ControllerResult(Generic[T]):
    """Result from a controller processing stage"""
    success: bool
    data: Optional[T] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: Optional[float] = None
    
    @classmethod
    def success_result(cls, data: T, metadata: Optional[Dict[str, Any]] = None) -> 'ControllerResult[T]':
        """Create a successful result"""
        return cls(success=True, data=data, metadata=metadata or {})
    
    @classmethod
    def error_result(cls, error_message: str, metadata: Optional[Dict[str, Any]] = None) -> 'ControllerResult[T]':
        """Create an error result"""
        return cls(success=False, error_message=error_message, metadata=metadata or {})

@dataclass
class ControllerConfig:
    """Configuration for a controller"""
    controller_id: str
    controller_type: str
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    input_sensors: List[str] = field(default_factory=list)
    input_controllers: List[str] = field(default_factory=list)
    output_name: Optional[str] = None

class ControllerStage(ABC):
    """Base class for controller stages following ProcessingStage pattern"""
    
    def __init__(self, controller_id: str, config: ControllerConfig):
        self.controller_id = controller_id
        self.config = config
        self.enabled = config.enabled
        self.controller_type = ControllerType.CUSTOM
        self.status = ControllerStatus.STOPPED
        self._processing_time = 0.0
        self._error_count = 0
        self._last_result: Optional[ControllerResult] = None
        self._output_cache: Dict[str, Any] = {}
    
    @abstractmethod
    async def process(self, input_data: ControllerInput) -> ControllerResult:
        """Process input data and return result"""
        pass
    
    async def process_with_timing(self, input_data: ControllerInput) -> ControllerResult:
        """Process data with performance timing"""
        if not self.enabled or self.status != ControllerStatus.RUNNING:
            return ControllerResult.success_result(None)
        
        start_time = time.time()
        try:
            result = await self.process(input_data)
            self._processing_time = (time.time() - start_time) * 1000  # Convert to ms
            result.processing_time_ms = self._processing_time
            
            if not result.success:
                self._error_count += 1
                self.status = ControllerStatus.ERROR
                error(f"Controller {self.controller_id} processing failed: {result.error_message}")
            else:
                # Cache successful results
                if result.data is not None:
                    self._output_cache[self.controller_id] = result.data
                
            self._last_result = result
            return result
            
        except Exception as e:
            self._processing_time = (time.time() - start_time) * 1000
            self._error_count += 1
            self.status = ControllerStatus.ERROR
            error_msg = f"Exception in controller {self.controller_id}: {e}"
            error(error_msg)
            result = ControllerResult.error_result(error_msg)
            result.processing_time_ms = self._processing_time
            self._last_result = result
            return result
    
    async def start(self) -> bool:
        """Start the controller"""
        try:
            if await self.initialize():
                self.status = ControllerStatus.RUNNING
                info(f"Started controller {self.controller_id}")
                return True
            else:
                self.status = ControllerStatus.ERROR
                error(f"Failed to initialize controller {self.controller_id}")
                return False
        except Exception as e:
            self.status = ControllerStatus.ERROR
            error(f"Error starting controller {self.controller_id}: {e}")
            return False
    
    async def stop(self) -> None:
        """Stop the controller"""
        try:
            await self.cleanup()
            self.status = ControllerStatus.STOPPED
            info(f"Stopped controller {self.controller_id}")
        except Exception as e:
            error(f"Error stopping controller {self.controller_id}: {e}")
    
    async def pause(self) -> None:
        """Pause the controller"""
        if self.status == ControllerStatus.RUNNING:
            self.status = ControllerStatus.PAUSED
            info(f"Paused controller {self.controller_id}")
    
    async def resume(self) -> None:
        """Resume the controller"""
        if self.status == ControllerStatus.PAUSED:
            self.status = ControllerStatus.RUNNING
            info(f"Resumed controller {self.controller_id}")
    
    async def initialize(self) -> bool:
        """Initialize the controller. Override in subclasses if needed."""
        return True
    
    async def cleanup(self) -> None:
        """Cleanup controller resources. Override in subclasses if needed."""
        pass
    
    def get_output(self) -> Optional[Any]:
        """Get the latest output from this controller"""
        return self._output_cache.get(self.controller_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get controller statistics"""
        return {
            'controller_id': self.controller_id,
            'enabled': self.enabled,
            'status': self.status.value,
            'controller_type': self.controller_type.value,
            'processing_time_ms': self._processing_time,
            'error_count': self._error_count,
            'last_processing_time': self._last_result.processing_time_ms if self._last_result else None,
            'last_success': self._last_result.success if self._last_result else None,
            'has_output': self.controller_id in self._output_cache
        }

class ImageController(ControllerStage):
    """Base class for image-based controllers"""
    
    def __init__(self, controller_id: str, config: ControllerConfig):
        super().__init__(controller_id, config)
        self.controller_type = ControllerType.MOTION_DETECTION
        
    @abstractmethod
    async def process_image(self, image_data: Any, metadata: Dict[str, Any]) -> ControllerResult:
        """Process image data"""
        pass
    
    async def process(self, input_data: ControllerInput) -> ControllerResult:
        """Process input data, extracting image data"""
        # Look for image data in sensor readings or controller data
        image_data = None
        metadata = input_data.metadata.copy()
        
        # Try to find image data from camera sensors
        for sensor_id, reading in input_data.sensor_data.items():
            image_data_attr = getattr(reading, 'image_data', None)
            if image_data_attr is not None:
                image_data = image_data_attr
                metadata['source_sensor'] = sensor_id
                metadata['timestamp'] = reading.timestamp
                break
        
        # Try controller data
        if image_data is None:
            for controller_id, data in input_data.controller_data.items():
                if isinstance(data, dict) and 'image' in data:
                    image_data = data['image']
                    metadata['source_controller'] = controller_id
                    break
        
        if image_data is None:
            return ControllerResult.error_result("No image data found in input")
        
        return await self.process_image(image_data, metadata)

class StateController(ControllerStage):
    """Base class for state derivation controllers"""
    
    def __init__(self, controller_id: str, config: ControllerConfig):
        super().__init__(controller_id, config)
        self.controller_type = ControllerType.STATE_DERIVATION
        
    @abstractmethod
    async def derive_state(self, sensor_data: Dict[str, SensorReading], 
                          controller_outputs: Dict[str, Any],
                          metadata: Dict[str, Any]) -> ControllerResult:
        """Derive state from sensor and controller data"""
        pass
    
    async def process(self, input_data: ControllerInput) -> ControllerResult:
        """Process input data for state derivation"""
        return await self.derive_state(
            input_data.sensor_data,
            input_data.controller_data,
            input_data.metadata
        )
