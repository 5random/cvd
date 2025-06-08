"""
Central sensor management service for handling sensor lifecycle and data collection.
"""
import asyncio
import importlib.metadata
from typing import Dict, List, Optional, Type, Callable, Any
from concurrent.futures import ThreadPoolExecutor, Executor
from src.data_handler.interface.sensor_interface import SensorInterface, SensorReading, SensorConfig, SensorStatus
from src.utils.config_utils.config_service import ConfigurationService, ValidationError
from src.data_handler.sources.sensors.arduino_tc_sensor import ArduinoTCSensor
from src.data_handler.sources.sensors.rs232_sensor import RS232Sensor
from src.data_handler.sources.mock_sensors import (
    MockArduinoTCSensor,
    MockRS232Sensor,
)
from src.utils.data_utils.data_saver import DataSaver
from src.data_handler.processing.pipeline.pipeline import DataPipeline
from src.utils.log_utils.log_service import info, warning, error, debug

# Registry for sensor implementations
SensorFactory = Callable[[SensorConfig, Optional[Executor]], SensorInterface]
SENSOR_REGISTRY: Dict[str, SensorFactory] = {
    'arduino_tc_board': ArduinoTCSensor,
    'rs232': RS232Sensor,
    'mock_arduino_tc_board': MockArduinoTCSensor,
    'mock_rs232': MockRS232Sensor,
}


def load_entry_point_sensors(group: str = 'cvd.sensors') -> None:
    """Load sensor implementations from entry points."""
    try:
        eps = importlib.metadata.entry_points()
        selected = eps.select(group=group) if hasattr(eps, 'select') else eps.get(group, [])
        for ep in selected:
            try:
                factory = ep.load()
                SENSOR_REGISTRY[ep.name] = factory
                info(f"Loaded sensor entry point: {ep.name}")
            except Exception as e:  # pragma: no cover - log only
                error(f"Failed to load sensor entry point {ep.name}: {e}")
    except Exception as e:  # pragma: no cover - log only
        warning(f"Could not load sensor entry points: {e}")


load_entry_point_sensors()

class SensorManager:
    """Manages sensor lifecycle, polling, and data collection"""
    
    def __init__(self,
                 config_service: ConfigurationService,
                 max_workers: int = 4,
                 data_saver: Optional[DataSaver] = None,
                 data_pipeline: Optional[DataPipeline] = None):
        self.config_service = config_service
        self._sensors: Dict[str, SensorInterface] = {}
        self._readings_cache: Dict[str, SensorReading] = {}
        self._polling_tasks: Dict[str, asyncio.Task] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown_event = asyncio.Event()
        self._new_data_event = asyncio.Event()
        # Unified data saver (raw & processed)
        self.data_saver = data_saver
        # Data processing pipeline
        self.data_pipeline = data_pipeline

    @property
    def executor(self) -> Executor:
        """Thread pool executor used for sensor operations."""
        return self._executor
        
    def register_sensor_type(self, sensor_type: str, factory: SensorFactory) -> None:
        """Register a new sensor type
        
        Args:
            sensor_type: Type identifier for the sensor
            factory: Factory function that creates sensor instances        """
        SENSOR_REGISTRY[sensor_type] = factory
        info(f"Registered sensor type: {sensor_type}")

    def create_sensor(self, sensor_config: Dict[str, Any]) -> Optional[SensorInterface]:
        """Create sensor instance from configuration
        
        Args:
            sensor_config: Sensor configuration dictionary
            
        Returns:
            SensorInterface instance or None if creation failed
        """
        try:            # Use 'source' field for sensor factory lookup, 'type' is for categorization
            source = sensor_config.get('source')
            sensor_type = sensor_config.get('type', 'unknown')
            
            if source not in SENSOR_REGISTRY:
                error(f"Unknown sensor source: {source}")
                return None
                
            # Create config object
            config = SensorConfig(
                sensor_id=sensor_config['sensor_id'],
                sensor_type=sensor_type,
                enabled=sensor_config.get('enabled', True),
                poll_interval_ms=sensor_config.get('poll_interval_ms', 1000),
                parameters={
                    'port': sensor_config.get('port'),
                    'channel': sensor_config.get('channel', 0),
                    'baudrate': sensor_config.get('baudrate', 9600),
                    'timeout': sensor_config.get('timeout', 2.0),
                    'interface': sensor_config.get('interface'),
                    'name': sensor_config.get('name')
                }
            )
            
            # Create sensor instance using source
            factory = SENSOR_REGISTRY[source]
            sensor = factory(config, self._executor)
            
            info(f"Created sensor: {config.sensor_id} ({sensor_type} from {source})")
            return sensor
            
        except Exception as e:
            error(f"Failed to create sensor: {e}")
            return None
    
    async def register_sensor(self, sensor: SensorInterface) -> bool:
        """Register and initialize a sensor
        
        Args:
            sensor: SensorInterface instance
            
        Returns:
            True if registration successful
        """
        try:
            # Initialize sensor
            if not await sensor.initialize():
                error(f"Failed to initialize sensor {sensor.sensor_id}")
                return False
            
            # Register sensor
            self._sensors[sensor.sensor_id] = sensor
            
            # Initialize cache entry
            self._readings_cache[sensor.sensor_id] = SensorReading.create_offline(sensor.sensor_id)
            
            info(f"Registered sensor: {sensor.sensor_id}")
            return True
            
        except Exception as e:
            error(f"Failed to register sensor {sensor.sensor_id}: {e}")
            return False
    
    async def start_sensor(self, sensor_id: str) -> bool:
        """Start polling for a sensor
        
        Args:
            sensor_id: ID of sensor to start
            
        Returns:
            True if polling started successfully
        """
        sensor = self._sensors.get(sensor_id)
        if not sensor:
            error(f"Sensor not found: {sensor_id}")
            return False
        
        if sensor_id in self._polling_tasks:
            warning(f"Sensor {sensor_id} is already polling")
            return True
        
        try:
            # Get polling interval from config
            sensor_configs = self.config_service.get_sensor_configs()
            # sensor_configs may be a dict or list of (id,config) tuples
            if sensor_configs is None:
                error(f"No sensor configurations available")
                return False
            try:
                if isinstance(sensor_configs, dict):
                    sensor_config = sensor_configs.get(sensor_id)
                else:
                    sensor_config = dict(sensor_configs).get(sensor_id)
            except (TypeError, ValueError) as e:
                error(f"Invalid sensor configuration format: {e}")
                return False
            
            if not sensor_config:
                error(f"No configuration found for sensor {sensor_id}")
                return False
            
            poll_interval = sensor_config.get('poll_interval_ms', 1000) / 1000.0
            
            # Start polling task
            task = asyncio.create_task(self._poll_sensor(sensor, poll_interval))
            self._polling_tasks[sensor_id] = task
            
            info(f"Started polling sensor {sensor_id} every {poll_interval}s")
            return True
            
        except Exception as e:
            error(f"Failed to start sensor {sensor_id}: {e}")
            return False
    
    async def stop_sensor(self, sensor_id: str) -> None:
        """Stop polling for a sensor
        
        Args:
            sensor_id: ID of sensor to stop
        """
        # Cancel polling task
        if sensor_id in self._polling_tasks:
            self._polling_tasks[sensor_id].cancel()
            try:
                await self._polling_tasks[sensor_id]
            except asyncio.CancelledError:
                pass
            del self._polling_tasks[sensor_id]
            info(f"Stopped polling sensor {sensor_id}")
        
        # Cleanup sensor
        sensor = self._sensors.get(sensor_id)
        if sensor:
            await sensor.cleanup()
    
    async def _poll_sensor(self, sensor: SensorInterface, interval: float) -> None:
        """Polling loop for a single sensor
        
        Args:
            sensor: Sensor to poll
            interval: Polling interval in seconds
        """
        while not self._shutdown_event.is_set():
            try:
                # Read sensor data
                reading = await sensor.read()
                
                # Update cache
                self._readings_cache[sensor.sensor_id] = reading
                self._new_data_event.set()
                # Persist raw reading
                if self.data_saver:
                    try:
                        self.data_saver.save(reading, category="raw")
                    except Exception as e:
                        error(f"DataSaver raw save error for {sensor.sensor_id}: {e}")
                # Process through pipeline and save processed data
                if self.data_pipeline and self.data_saver:
                    try:
                        result = await self.data_pipeline.process(reading)
                        if result.success and isinstance(result.data, SensorReading):
                            self.data_saver.save(result.data, category="processed")
                        elif not result.success:
                            warning(f"Pipeline error for {sensor.sensor_id}: {result.error_message}")
                    except Exception as e:
                        error(f"DataSaver processed save error for {sensor.sensor_id}: {e}")
                 # Log errors
                if reading.status != SensorStatus.OK:
                    warning(f"Sensor {sensor.sensor_id} status: {reading.status}")
                
                # Wait for next poll
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                error(f"Error polling sensor {sensor.sensor_id}: {e}")
                # Create error reading
                error_reading = SensorReading.create_error(sensor.sensor_id, str(e))
                self._readings_cache[sensor.sensor_id] = error_reading
                await asyncio.sleep(interval)
    
    def get_latest_readings(self) -> Dict[str, SensorReading]:
        """Get latest readings from all sensors

        Returns:
            Dictionary mapping sensor IDs to their latest readings
        """
        return dict(self._readings_cache)

    async def wait_for_new_data(self, timeout: Optional[float] = None) -> bool:
        """Wait until new sensor data is available or timeout expires.

        Args:
            timeout: Optional timeout in seconds.

        Returns:
            True if new data was received before the timeout, False otherwise.
        """
        try:
            await asyncio.wait_for(self._new_data_event.wait(), timeout=timeout)
            self._new_data_event.clear()
            return True
        except asyncio.TimeoutError:
            return False
    
    def get_sensor_reading(self, sensor_id: str) -> Optional[SensorReading]:
        """Get latest reading from specific sensor
        
        Args:
            sensor_id: ID of sensor
            
        Returns:
            Latest SensorReading or None if sensor not found
        """
        return self._readings_cache.get(sensor_id)
    
    def get_active_sensors(self) -> List[str]:
        """Get list of active sensor IDs
        
        Returns:
            List of sensor IDs that are currently polling
        """
        return list(self._polling_tasks.keys())
    
    def get_all_sensors(self) -> List[str]:
        """Get list of all registered sensor IDs
        
        Returns:
            List of all registered sensor IDs
        """
        return list(self._sensors.keys())
    
    async def start_all_configured_sensors(self) -> int:
        """Start all sensors from configuration
        
        Returns:
            Number of sensors successfully started
        """
        sensor_configs = self.config_service.get_sensor_configs()
        started_count = 0

        # Validate and normalize sensor configuration iterable
        if sensor_configs is None:
            warning("No sensor configurations found")
            return 0
        try:
            if isinstance(sensor_configs, dict):
                config_list = list(sensor_configs.values())
            elif isinstance(sensor_configs, list):
                config_list = []
                for entry in sensor_configs:
                    if isinstance(entry, (list, tuple)) and len(entry) == 2:
                        config_list.append(entry[1])
                    else:
                        error(f"Invalid sensor configuration entry: {entry}")
                if not config_list:
                    warning("No valid sensor configuration entries found")
            else:
                error(f"Unexpected sensor configuration type: {type(sensor_configs)}")
                return 0
        except (TypeError, ValueError) as e:
            error(f"Failed to parse sensor configurations: {e}")
            return 0

        for sensor_config in config_list:
            if not sensor_config.get('enabled', True):
                continue
            try:
                # Validate configuration
                self.config_service.validate_sensor_config(sensor_config)
            except ValidationError as ve:
                error(
                    f"Sensor config validation error for {sensor_config.get('sensor_id', 'unknown')}: {ve}"
                )
                continue
            try:
                # Create sensor
                sensor = self.create_sensor(sensor_config)
                if not sensor:
                    continue

                # Register and start sensor
                if await self.register_sensor(sensor):
                    if await self.start_sensor(sensor.sensor_id):
                        started_count += 1

            except Exception as e:
                error(f"Failed to start sensor {sensor_config.get('sensor_id', 'unknown')}: {e}")
        
        info(f"Started {started_count} sensors")
        return started_count
    
    async def shutdown(self) -> None:
        """Shutdown all sensors and polling tasks"""
        info("Shutting down sensor manager...")

        # Signal shutdown
        self._shutdown_event.set()
        self._new_data_event.set()
        
        # Stop all sensors
        for sensor_id in list(self._sensors.keys()):
            await self.stop_sensor(sensor_id)
        
        # Shutdown thread pool
        self._executor.shutdown(wait=True)
        # Flush and close data saver
        if self.data_saver:
            try:
                self.data_saver.flush_all()
                self.data_saver.close()
            except Exception as e:
                error(f"DataSaver finalize error: {e}")
         
        info("Sensor manager shutdown complete")
    
    def get_sensor_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status information for all sensors
        
        Returns:
            Dictionary with sensor status information
        """
        status = {}
        for sensor_id, sensor in self._sensors.items():
            reading = self._readings_cache.get(sensor_id)
            status[sensor_id] = {
                'connected': sensor.is_connected,
                'polling': sensor_id in self._polling_tasks,
                'last_reading': reading.timestamp if reading else None,
                'status': reading.status.value if reading else 'unknown',
                'sensor_type': sensor.sensor_type
            }
        return status
