from typing import Optional

from src.data_handler.processing.processing_base import (
    ProcessingResult,
    ProcessingStage,
    ProcessingStageType,
)
from src.data_handler.interface.sensor_interface import SensorReading, SensorStatus

class RangeValidationFilter(ProcessingStage):
    """Validate sensor readings are within expected range"""
    
    def __init__(self, stage_id: str, min_value: Optional[float] = None, max_value: Optional[float] = None):
        super().__init__(stage_id)
        self.stage_type = ProcessingStageType.VALIDATE
        self.min_value = min_value
        self.max_value = max_value
    
    async def process(self, data: SensorReading) -> ProcessingResult[SensorReading]:
        """Validate reading is within range"""
        if data.value is None or data.status != SensorStatus.OK:
            return ProcessingResult.success_result(data)
        
        # Check range
        value_valid = True
        error_msgs = []
        
        if self.min_value is not None and data.value < self.min_value:
            value_valid = False
            error_msgs.append(f"Value {data.value} below minimum {self.min_value}")
        
        if self.max_value is not None and data.value > self.max_value:
            value_valid = False
            error_msgs.append(f"Value {data.value} above maximum {self.max_value}")
        
        if not value_valid:
            # instantiate using positional args to satisfy dataclass __init__
            invalid_reading = SensorReading(
                data.sensor_id,
                None,
                data.timestamp,
                SensorStatus.ERROR,
                "; ".join(error_msgs),
                {
                    **data.metadata,
                    'filter_applied': 'range_validation',
                    'original_value': data.value,
                    'min_allowed': self.min_value,
                    'max_allowed': self.max_value
                }
            )
            return ProcessingResult.success_result(invalid_reading)
        
        return ProcessingResult.success_result(data)
