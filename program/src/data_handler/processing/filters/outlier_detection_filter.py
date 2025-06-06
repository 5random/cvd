from typing import Dict, List

from src.data_handler.processing.processing_base import (
    ProcessingResult,
    ProcessingStage,
    ProcessingStageType,
)
from src.data_handler.interface.sensor_interface import SensorReading, SensorStatus



class OutlierDetectionFilter(ProcessingStage):
    """Outlier detection and removal filter"""
    
    def __init__(self, stage_id: str, threshold_std: float = 2.0, min_samples: int = 10):
        super().__init__(stage_id)
        self.stage_type = ProcessingStageType.VALIDATE
        self.threshold_std = threshold_std
        self.min_samples = min_samples
        self._data_history: Dict[str, List[float]] = {}
    
    async def process(self, data: SensorReading) -> ProcessingResult[SensorReading]:
        """Detect and filter outliers"""
        if data.value is None or data.status != SensorStatus.OK:
            return ProcessingResult.success_result(data)
        
        # Initialize history for sensor if needed
        if data.sensor_id not in self._data_history:
            self._data_history[data.sensor_id] = []
        
        history = self._data_history[data.sensor_id]
        
        # Check if we have enough samples for outlier detection
        if len(history) < self.min_samples:
            history.append(data.value)
            return ProcessingResult.success_result(data)
        
        # Calculate statistics
        mean_val = sum(history) / len(history)
        variance = sum((x - mean_val) ** 2 for x in history) / len(history)
        std_dev = variance ** 0.5
        
        # Check if current value is an outlier
        if std_dev > 0:
            z_score = abs(data.value - mean_val) / std_dev
            
            if z_score > self.threshold_std:
                # Value is an outlier
                outlier_reading = SensorReading(
                    sensor_id=data.sensor_id,
                    value=None,
                    timestamp=data.timestamp,
                    status=SensorStatus.ERROR,
                    error_message=f"Outlier detected (z-score: {z_score:.2f})",
                    metadata={
                        **data.metadata,
                        'filter_applied': 'outlier_detection',
                        'z_score': z_score,
                        'original_value': data.value,
                        'mean': mean_val,
                        'std_dev': std_dev
                    }
                )
                
                # Don't add outlier to history
                return ProcessingResult.success_result(outlier_reading)
        
        # Value is normal, add to history
        history.append(data.value)
        
        # Keep history size manageable
        if len(history) > self.min_samples * 2:
            history.pop(0)
        
        return ProcessingResult.success_result(data)