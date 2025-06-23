"""
Data processing pipeline for sensor data filtering and transformation.
"""
from typing import Dict, List, Any, Optional

from cvd.data_handler.processing.processing_base import ProcessingResult, ProcessingStage
from cvd.data_handler.processing.filters.simple_moving_avg_filter import MovingAverageFilter
from cvd.data_handler.processing.filters.range_validation_filter import RangeValidationFilter
from cvd.data_handler.processing.filters.outlier_detection_filter import OutlierDetectionFilter
from cvd.utils.log_service import info, warning

class DataPipeline:
    """Data processing pipeline managing multiple stages"""
    
    def __init__(self, pipeline_id: str):
        self.pipeline_id = pipeline_id
        self._stages: List[ProcessingStage] = []
        self._stage_dict: Dict[str, ProcessingStage] = {}
        self._total_processed = 0
        self._total_errors = 0
    
    def add_stage(self, stage: ProcessingStage) -> None:
        """Add processing stage to pipeline"""
        if stage.stage_id in self._stage_dict:
            raise ValueError(f"Stage with ID '{stage.stage_id}' already exists")
        
        self._stages.append(stage)
        self._stage_dict[stage.stage_id] = stage
        info(f"Added processing stage {stage.stage_id} to pipeline {self.pipeline_id}")
    
    def remove_stage(self, stage_id: str) -> bool:
        """Remove processing stage from pipeline"""
        if stage_id not in self._stage_dict:
            return False
        
        stage = self._stage_dict[stage_id]
        self._stages.remove(stage)
        del self._stage_dict[stage_id]
        info(f"Removed processing stage {stage_id} from pipeline {self.pipeline_id}")
        return True
    
    def get_stage(self, stage_id: str) -> Optional[ProcessingStage]:
        """Get processing stage by ID"""
        return self._stage_dict.get(stage_id)
    
    def set_stage_enabled(self, stage_id: str, enabled: bool) -> bool:
        """Enable/disable processing stage"""
        stage = self._stage_dict.get(stage_id)
        if stage:
            stage.enabled = enabled
            return True
        return False
    
    async def process(self, data: Any) -> ProcessingResult:
        """Process data through all pipeline stages"""
        self._total_processed += 1
        current_data = data
        
        for stage in self._stages:
            if not stage.enabled:
                continue
            
            result = await stage.process_with_timing(current_data)
            
            if not result.success:
                self._total_errors += 1
                warning(f"Processing failed in stage {stage.stage_id}: {result.error_message}")
                return result
            
            current_data = result.data
        
        return ProcessingResult.success_result(current_data)
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        stage_stats = [stage.get_stats() for stage in self._stages]
        
        return {
            'pipeline_id': self.pipeline_id,
            'total_processed': self._total_processed,
            'total_errors': self._total_errors,
            'success_rate': (self._total_processed - self._total_errors) / max(1, self._total_processed),
            'stages': stage_stats
        }
    
    def clear_stats(self) -> None:
        """Clear pipeline statistics"""
        self._total_processed = 0
        self._total_errors = 0
        for stage in self._stages:
            stage._error_count = 0
            stage._processing_time = 0.0

# Factory functions for common pipeline configurations

def create_temperature_pipeline(pipeline_id: str) -> DataPipeline:
    """Create a pipeline optimized for temperature sensor data"""
    pipeline = DataPipeline(pipeline_id)
    
    # Range validation (typical temperature ranges)
    pipeline.add_stage(RangeValidationFilter(
        "range_validation",
        min_value=-50.0,
        max_value=200.0
    ))
    
    # Outlier detection
    pipeline.add_stage(OutlierDetectionFilter(
        "outlier_detection",
        threshold_std=2.5,
        min_samples=10
    ))
    
    # Moving average smoothing
    pipeline.add_stage(MovingAverageFilter(
        "moving_average",
        window_size=5
    ))
    
    return pipeline

def create_minimal_pipeline(pipeline_id: str) -> DataPipeline:
    """Create a minimal pipeline with basic validation"""
    pipeline = DataPipeline(pipeline_id)
    
    # Only range validation
    pipeline.add_stage(RangeValidationFilter(
        "range_validation",
        min_value=-273.15,  # Absolute zero
        max_value=1000.0    # Very high temperature
    ))
    
    return pipeline
