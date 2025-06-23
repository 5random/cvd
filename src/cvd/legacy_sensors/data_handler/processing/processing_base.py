from typing import Any, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import time

from cvd.utils.log_service import error

T = TypeVar('T')

class ProcessingStageType(Enum):
    """Types of processing stages"""
    FILTER = "filter"
    TRANSFORM = "transform"
    VALIDATE = "validate"
    AGGREGATE = "aggregate"

@dataclass
class ProcessingResult(Generic[T]):
    """Result from a processing stage"""
    success: bool
    data: Optional[T] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success_result(cls, data: T, metadata: Optional[Dict[str, Any]] = None) -> 'ProcessingResult[T]':
        """Create a successful result"""
        return cls(success=True, data=data, metadata=metadata or {})
    
    @classmethod
    def error_result(cls, error_message: str) -> 'ProcessingResult[T]':
        """Create an error result"""
        return cls(success=False, error_message=error_message)

class ProcessingStage(ABC):
    """Base class for data processing stages"""
    
    def __init__(self, stage_id: str, enabled: bool = True):
        self.stage_id = stage_id
        self.enabled = enabled
        self.stage_type = ProcessingStageType.FILTER
        self._processing_time = 0.0
        self._error_count = 0
    
    @abstractmethod
    async def process(self, data: Any) -> ProcessingResult:
        """Process input data and return result"""
        pass
    
    async def process_with_timing(self, data: Any) -> ProcessingResult:
        """Process data with performance timing"""
        if not self.enabled:
            return ProcessingResult.success_result(data)
        
        start_time = time.time()
        try:
            result = await self.process(data)
            self._processing_time = time.time() - start_time
            
            if not result.success:
                self._error_count += 1
            
            return result
        except Exception as e:
            self._processing_time = time.time() - start_time
            self._error_count += 1
            error(f"Error in processing stage {self.stage_id}: {e}")
            return ProcessingResult.error_result(str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            'stage_id': self.stage_id,
            'enabled': self.enabled,
            'stage_type': self.stage_type.value,
            'processing_time_ms': self._processing_time * 1000,
            'error_count': self._error_count
        }
