"""
Reactor State Controller - Derives reactor operational states from sensor data and motion detection.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import time

from src.controllers.controller_base import StateController, ControllerConfig, ControllerResult
from src.data_handler.interface.sensor_interface import SensorReading
from src.utils.log_utils.log_service import info, warning, error, debug

class ReactorState(Enum):
    """Reactor operational states"""
    IDLE = "idle"
    HEATING = "heating"
    PROCESSING = "processing"  
    COOLING = "cooling"
    ALARM = "alarm"
    UNKNOWN = "unknown"


class ReactorAlarmType(Enum):
    """Types of reactor alarms"""
    OVERTEMPERATURE = "overtemperature"
    UNDERTEMPERATURE = "undertemperature"
    SENSOR_FAILURE = "sensor_failure"
    MOTION_ANOMALY = "motion_anomaly"
    TEMPERATURE_GRADIENT = "temperature_gradient"
    NO_DATA = "no_data"


@dataclass
class ReactorStateData:
    """Reactor state information"""
    state: ReactorState
    confidence: float  # 0.0 to 1.0
    primary_temperature: Optional[float]
    temperature_sensors: Dict[str, Optional[float]]  # allow None for invalid readings
    motion_detected: bool
    alarms: List[ReactorAlarmType]
    state_duration: float  # seconds in current state
    metadata: Dict[str, Any]


@dataclass
class ReactorStateConfig:
    """Configuration for reactor state derivation"""
    # Temperature thresholds (°C)
    idle_temp_max: float = 35.0
    heating_temp_min: float = 40.0
    processing_temp_min: float = 80.0
    processing_temp_max: float = 150.0
    alarm_temp_max: float = 200.0
    alarm_temp_min: float = 0.0
    
    # Temperature gradient thresholds
    max_temp_gradient: float = 50.0  # Max °C difference between sensors
    min_sensor_count: int = 1
    
    # State transition timing
    min_state_duration: float = 5.0  # Minimum seconds before state change
    confidence_threshold: float = 0.7
    
    # Motion detection integration
    motion_required_for_processing: bool = True
    motion_alarm_threshold: float = 30.0  # seconds of no motion in processing
    
    # Sensor health monitoring
    max_sensor_age: float = 10.0  # Max seconds for valid sensor data
    min_valid_sensors: int = 1


class ReactorStateController(StateController):
    """Controller for deriving reactor operational states"""
    
    def __init__(self, controller_id: str = "reactor_state", config: Optional[ControllerConfig] = None):
        # Ensure we always pass a valid ControllerConfig to the base class
        if config is None:
            config = ControllerConfig(controller_id=controller_id,
                                      controller_type="reactor_state")
        super().__init__(controller_id, config)
        
        # Start with default configuration values
        defaults = ReactorStateConfig()

        # Apply parameters from provided ControllerConfig
        params = config.parameters
        for key, value in params.items():
            if hasattr(defaults, key):
                setattr(defaults, key, value)

        self.reactor_config = defaults
        
        # State tracking
        self._current_state = ReactorState.UNKNOWN
        self._state_start_time = time.time()
        self._last_motion_time: Optional[float] = None
        self._state_history: List[tuple] = []  # (timestamp, state, confidence)
        
        # Statistics
        self._state_transitions = 0
        self._alarm_count = 0
        
    async def derive_state(self, 
                          sensor_data: Dict[str, SensorReading], 
                          controller_outputs: Dict[str, Any],
                          metadata: Dict[str, Any]) -> ControllerResult:
        """Derive reactor state from sensor and controller data"""
        try:
            current_time = time.time()
            
            # Extract temperature data
            temp_sensors = self._extract_temperature_data(sensor_data, current_time)
            
            # Extract motion detection data
            motion_detected = self._extract_motion_data(controller_outputs)
            
            # Check for alarms
            alarms = self._check_alarms(temp_sensors, motion_detected, current_time)
            
            # Derive reactor state
            new_state, confidence = self._derive_reactor_state(
                temp_sensors, motion_detected, alarms, current_time
            )
            
            # Update state tracking
            state_duration = self._update_state_tracking(new_state, current_time)
            
            # Create result data
            if alarms:
                # Increment total alarm count by number of new alarms detected
                self._alarm_count += len(alarms)
            result_data = ReactorStateData(
                state=new_state,
                confidence=confidence,
                primary_temperature=self._get_primary_temperature(temp_sensors),
                temperature_sensors=temp_sensors,
                motion_detected=motion_detected,
                alarms=alarms,
                state_duration=state_duration,
                metadata={
                    'controller_id': self.controller_id,
                    'timestamp': current_time,
                    'sensor_count': len(temp_sensors),
                    'valid_sensors': len([t for t in temp_sensors.values() if t is not None]),
                    'state_transitions': self._state_transitions,
                    'alarm_count': self._alarm_count
                }
            )
            
            # Update statistics
            # internal counters are tracked separately
            
            return ControllerResult(
                success=True,
                data=result_data,
                metadata={
                    'controller_type': 'reactor_state',
                    'state': new_state.value,
                    'confidence': confidence,
                    'alarms': [alarm.value for alarm in alarms]
                }
            )
            
        except Exception as e:
            error(f"Error in reactor state derivation: {e}")
            return ControllerResult.error_result(f"Reactor state derivation failed: {e}")
    
    def _extract_temperature_data(self, sensor_data: Dict[str, SensorReading], current_time: float) -> Dict[str, Optional[float]]:
        """Extract valid temperature data from sensor readings"""
        temp_data = {}
        
        for sensor_id, reading in sensor_data.items():
            if reading is None:
                temp_data[sensor_id] = None
                continue
                
            # Check sensor age
            age = current_time - reading.timestamp
            if age > self.reactor_config.max_sensor_age:
                temp_data[sensor_id] = None
                continue
            
            # Check sensor status and value validity
            if reading.is_valid() and reading.value is not None:
                # Basic temperature range validation
                if -50.0 <= reading.value <= 300.0:  # Reasonable temperature range
                    temp_data[sensor_id] = reading.value
                else:
                    temp_data[sensor_id] = None
            else:
                temp_data[sensor_id] = None
        
        return temp_data
    
    def _extract_motion_data(self, controller_outputs: Dict[str, Any]) -> bool:
        """Extract motion detection status from controller outputs"""
        motion_detected = False

        for _, output in controller_outputs.items():
            controller_type = None
            data = output

            if isinstance(output, dict):
                controller_type = output.get('controller_type')
                if 'metadata' in output and isinstance(output['metadata'], dict):
                    controller_type = output['metadata'].get('controller_type', controller_type)
                if 'data' in output:
                    data = output['data']
            else:
                controller_type = getattr(output, 'controller_type', None)
                if hasattr(output, 'metadata') and isinstance(output.metadata, dict):
                    controller_type = output.metadata.get('controller_type', controller_type)
                data = getattr(output, 'data', data)

            if controller_type == 'motion_detection':
                if isinstance(data, dict) and 'motion_detected' in data:
                    motion_detected = bool(data['motion_detected'])
                elif isinstance(data, bool):
                    motion_detected = bool(data)
                elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], dict):
                    if 'motion_detected' in data['data']:
                        motion_detected = bool(data['data']['motion_detected'])
                break

        # Update motion tracking
        if motion_detected:
            self._last_motion_time = time.time()

        return motion_detected
    
    def _check_alarms(self, temp_sensors: Dict[str, Optional[float]], 
                     motion_detected: bool, current_time: float) -> List[ReactorAlarmType]:
        """Check for alarm conditions"""
        alarms = []
        
        # Get valid temperatures
        valid_temps = [t for t in temp_sensors.values() if t is not None]
        
        # Check if we have enough sensor data
        if len(valid_temps) < self.reactor_config.min_valid_sensors:
            alarms.append(ReactorAlarmType.SENSOR_FAILURE)
        
        if len(valid_temps) == 0:
            alarms.append(ReactorAlarmType.NO_DATA)
            return alarms
        
        # Temperature alarms
        max_temp = max(valid_temps)
        min_temp = min(valid_temps)
        
        if max_temp > self.reactor_config.alarm_temp_max:
            alarms.append(ReactorAlarmType.OVERTEMPERATURE)
        
        if min_temp < self.reactor_config.alarm_temp_min:
            alarms.append(ReactorAlarmType.UNDERTEMPERATURE)
        
        # Temperature gradient alarm
        if len(valid_temps) > 1:
            temp_gradient = max_temp - min_temp
            if temp_gradient > self.reactor_config.max_temp_gradient:
                alarms.append(ReactorAlarmType.TEMPERATURE_GRADIENT)
        
        # Motion alarms during processing
        if (self._current_state == ReactorState.PROCESSING and 
            self.reactor_config.motion_required_for_processing):
            if self._last_motion_time is not None:
                time_since_motion = current_time - self._last_motion_time
                if time_since_motion > self.reactor_config.motion_alarm_threshold:
                    alarms.append(ReactorAlarmType.MOTION_ANOMALY)
        
        return alarms
    
    def _derive_reactor_state(self, temp_sensors: Dict[str, Optional[float]], 
                             motion_detected: bool, alarms: List[ReactorAlarmType],
                             current_time: float) -> tuple[ReactorState, float]:
        """Derive reactor state from current conditions"""
        
        # Get valid temperatures
        valid_temps = [t for t in temp_sensors.values() if t is not None]
        
        if not valid_temps:
            return ReactorState.UNKNOWN, 0.0
        
        primary_temp = self._get_primary_temperature(temp_sensors)
        if primary_temp is None:
            return ReactorState.UNKNOWN, 0.0
        
        # Check for alarm state first
        critical_alarms = [
            ReactorAlarmType.OVERTEMPERATURE,
            ReactorAlarmType.TEMPERATURE_GRADIENT,
            ReactorAlarmType.SENSOR_FAILURE
        ]
        
        if any(alarm in alarms for alarm in critical_alarms):
            return ReactorState.ALARM, 0.95
        
        # State logic based on temperature and motion
        confidence = 0.8  # Base confidence
        
        # Idle state: low temperature, minimal motion
        if primary_temp <= self.reactor_config.idle_temp_max:
            return ReactorState.IDLE, confidence
        
        # Heating state: rising temperature, may have motion
        elif (self.reactor_config.idle_temp_max < primary_temp < self.reactor_config.processing_temp_min):
            # Check if temperature is rising (simple heuristic)
            if self._is_temperature_rising(primary_temp):
                return ReactorState.HEATING, confidence
            else:
                return ReactorState.COOLING, confidence - 0.1
        
        # Processing state: high temperature, motion expected
        elif (self.reactor_config.processing_temp_min <= primary_temp <= self.reactor_config.processing_temp_max):
            if self.reactor_config.motion_required_for_processing:
                if motion_detected or self._recent_motion(current_time):
                    return ReactorState.PROCESSING, confidence
                else:
                    # High temp but no motion - could be heating or cooling
                    return ReactorState.HEATING, confidence - 0.2
            else:
                return ReactorState.PROCESSING, confidence
        
        # Very high temperature - could be alarm or extreme processing
        elif primary_temp > self.reactor_config.processing_temp_max:
            if primary_temp > self.reactor_config.alarm_temp_max * 0.9:  # Near alarm threshold
                return ReactorState.ALARM, 0.9
            else:
                return ReactorState.PROCESSING, confidence - 0.1
        
        return ReactorState.UNKNOWN, 0.3
    
    def _get_primary_temperature(self, temp_sensors: Dict[str, Optional[float]]) -> Optional[float]:
        """Get primary temperature reading (average of valid sensors)"""
        valid_temps = [t for t in temp_sensors.values() if t is not None]
        
        if not valid_temps:
            return None
        
        # Use average of all valid sensors as primary temperature
        return sum(valid_temps) / len(valid_temps)
    
    def _is_temperature_rising(self, current_temp: float) -> bool:
        """Determine if temperature is rising by comparing to last reading"""
        # If no previous temperature stored, assume rising
        if not hasattr(self, '_last_temp') or self._last_temp is None:
            rising = True
        else:
            rising = current_temp > self._last_temp
        # Store current temperature for next comparison
        self._last_temp = current_temp
        return rising
    
    def _recent_motion(self, current_time: float) -> bool:
        """Check if there was recent motion"""
        if self._last_motion_time is None:
            return False
        
        time_since_motion = current_time - self._last_motion_time
        return time_since_motion <= self.reactor_config.motion_alarm_threshold / 2
    
    def _update_state_tracking(self, new_state: ReactorState, current_time: float) -> float:
        """Update state tracking and return state duration"""
        state_duration = current_time - self._state_start_time
        
        # Check for state change
        if new_state != self._current_state:
            # Only change state if minimum duration has passed or it's an alarm
            if (state_duration >= self.reactor_config.min_state_duration or 
                new_state == ReactorState.ALARM):
                
                # Record state transition
                self._state_history.append((current_time, self._current_state, state_duration))
                
                # Keep only recent history (last 100 entries)
                if len(self._state_history) > 100:
                    self._state_history = self._state_history[-100:]
                
                # Update current state
                self._current_state = new_state
                self._state_start_time = current_time
                self._state_transitions += 1
                state_duration = 0.0
                
                info(f"Reactor state changed to {new_state.value} (transition #{self._state_transitions})")
        
        return state_duration
    
    async def get_status(self) -> Dict[str, Any]:
        """Get controller status information"""
        # Get base stats
        base_status = self.get_stats()
        
        reactor_status = {
            'current_state': self._current_state.value,
            'state_duration': time.time() - self._state_start_time,
            'state_transitions': self._state_transitions,
            'alarm_count': self._alarm_count,
            'last_motion_time': self._last_motion_time,
            'config': {
                'idle_temp_max': self.reactor_config.idle_temp_max,
                'processing_temp_min': self.reactor_config.processing_temp_min,
                'processing_temp_max': self.reactor_config.processing_temp_max,
                'alarm_temp_max': self.reactor_config.alarm_temp_max,
                'motion_required': self.reactor_config.motion_required_for_processing
            }
        }
        
        base_status.update(reactor_status)
        return base_status
    
    async def reset(self) -> None:
        """Reset controller state"""
        self._current_state = ReactorState.UNKNOWN
        self._state_start_time = time.time()
        self._last_motion_time = None
        self._state_history.clear()
        self._state_transitions = 0
        self._alarm_count = 0
        info("Reactor state controller reset")
