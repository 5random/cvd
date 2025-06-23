from typing import Dict, Deque
from collections import deque

from cvd.data_handler.processing.processing_base import (
    ProcessingResult,
    ProcessingStage,
    ProcessingStageType,
)
from cvd.data_handler.interface.sensor_interface import SensorReading, SensorStatus



class MovingAverageFilter(ProcessingStage):
    """Moving average filter for sensor readings"""
    
    def __init__(self, stage_id: str, window_size: int = 5):
        super().__init__(stage_id)
        if window_size <= 0:
            raise ValueError("window_size must be greater than 0")
        self.stage_type = ProcessingStageType.FILTER
        self.window_size = window_size
        self._data_windows: Dict[str, Deque[float]] = {}
    
    async def process(self, data: SensorReading) -> ProcessingResult[SensorReading]:
        """Apply moving average filter to sensor reading"""
        if data.value is None or data.status != SensorStatus.OK:
            return ProcessingResult.success_result(data)
        
        # Initialize window for sensor if needed
        if data.sensor_id not in self._data_windows:
            self._data_windows[data.sensor_id] = deque(maxlen=self.window_size)
        
        window = self._data_windows[data.sensor_id]
        
        # Add new value
        window.append(data.value)
        
        # Calculate moving average
        if len(window) >= self.window_size:
            averaged_value = sum(window) / len(window)
            
            # Create new reading with filtered value
            filtered_reading = SensorReading(
                sensor_id=data.sensor_id,
                value=averaged_value,
                timestamp=data.timestamp,
                status=data.status,
                error_message=data.error_message,
                metadata={
                    **data.metadata,
                    'filter_applied': 'moving_average',
                    'window_size': self.window_size,
                    'original_value': data.value
                }
            )
            
            return ProcessingResult.success_result(filtered_reading)
        else:
            # Not enough data points yet
            return ProcessingResult.success_result(data)
