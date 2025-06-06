"""
Dashboard component for displaying sensor data and system status.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from nicegui import ui
import time

from src.utils.config_utils.config_service import ConfigurationService
from src.utils.log_utils.log_service import info, warning, error, debug

from src.data_handler.sources.sensor_source_manager import SensorManager
from src.data_handler.interface.sensor_interface import SensorReading, SensorStatus
from src.gui.gui_tab_components.gui_tab_base_component import (
    BaseComponent,
    ComponentConfig,
    get_component_registry,
)
from src.gui.gui_elements.gui_webcam_stream_element import CameraStreamComponent
from src.controllers.controller_manager import ControllerManager
from src.controllers.controller_base import ControllerStatus

@dataclass
class SensorCardConfig:
    """Configuration for sensor display cards"""
    sensor_id: str
    title: str
    unit: str = "°C"
    precision: int = 1
    warning_threshold: Optional[float] = None
    error_threshold: Optional[float] = None

class SensorCardComponent(BaseComponent):
    """Individual sensor display card"""
    
    def __init__(self, config: ComponentConfig, sensor_config: SensorCardConfig, sensor_manager: SensorManager):
        super().__init__(config)
        self.sensor_config = sensor_config
        self.sensor_manager = sensor_manager
        self._value_label: Optional[ui.label] = None
        self._status_icon: Optional[ui.icon] = None
        self._timestamp_label: Optional[ui.label] = None
        self._update_timer: Optional[ui.timer] = None
    
    def render(self) -> ui.card:
        """Render sensor card"""
        with ui.card().classes('p-4 cvd-card min-w-48') as card:
            # Header with title and status
            with ui.row().classes('w-full items-center mb-2'):
                ui.label(self.sensor_config.title).classes('text-lg font-semibold flex-grow')
                self._status_icon = ui.icon('circle', size='sm').classes('ml-2')
            
            # Value display
            with ui.row().classes('w-full items-baseline'):
                self._value_label = ui.label('--').classes('cvd-sensor-value text-2xl')
                ui.label(self.sensor_config.unit).classes('text-sm text-gray-500 ml-1')
            
            # Timestamp
            self._timestamp_label = ui.label('No data').classes('text-xs text-gray-400 mt-1')
            
            # Start update timer
            self._update_timer = ui.timer(1.0, self._update_display)
        
        return card
    
    def _update_display(self) -> None:
        """Update sensor display with latest reading"""
        try:
            reading = self.sensor_manager.get_sensor_reading(self.sensor_config.sensor_id)
            
            if reading:
                self._update_value(reading)
                self._update_status(reading)
                self._update_timestamp(reading)
            else:
                self._show_no_data()
        except Exception as e:
            error(f"Error updating sensor card {self.sensor_config.sensor_id}: {e}")
    
    def _update_value(self, reading: SensorReading) -> None:
        """Update value display"""
        if self._value_label and reading.value is not None:
            formatted_value = f"{reading.value:.{self.sensor_config.precision}f}"
            self._value_label.text = formatted_value
            
            # Apply color based on thresholds
            color_class = self._get_value_color(reading.value)
            self._value_label.classes(replace=f'cvd-sensor-value text-2xl {color_class}')
    
    def _update_status(self, reading: SensorReading) -> None:
        """Update status icon"""
        if not self._status_icon:
            return
            
        status_config = {
            SensorStatus.OK: ('check_circle', 'text-green-500'),
            SensorStatus.ERROR: ('error', 'text-red-500'),
            SensorStatus.OFFLINE: ('radio_button_unchecked', 'text-gray-400'),
            SensorStatus.CALIBRATING: ('schedule', 'text-yellow-500'),
            SensorStatus.TIMEOUT: ('timer_off', 'text-orange-500')
        }
        
        icon, color = status_config.get(reading.status, ('help', 'text-gray-400'))
        self._status_icon.name = icon
        self._status_icon.classes(replace=color)
    
    def _update_timestamp(self, reading: SensorReading) -> None:
        """Update timestamp display"""
        if self._timestamp_label:
            time_diff = time.time() - reading.timestamp
            if time_diff < 60:
                time_str = f"{int(time_diff)}s ago"
            elif time_diff < 3600:
                time_str = f"{int(time_diff/60)}m ago"
            else:
                time_str = f"{int(time_diff/3600)}h ago"
            
            self._timestamp_label.text = time_str
    
    def _get_value_color(self, value: float) -> str:
        """Get color class based on value thresholds"""
        if self.sensor_config.error_threshold and value >= self.sensor_config.error_threshold:
            return 'text-red-500'
        elif self.sensor_config.warning_threshold and value >= self.sensor_config.warning_threshold:
            return 'text-yellow-500'
        else:
            return 'text-green-600'
    
    def _show_no_data(self) -> None:
        """Show no data state"""
        if self._value_label:
            self._value_label.text = '--'
        if self._status_icon:
            self._status_icon.name = 'radio_button_unchecked'
            self._status_icon.classes(replace='text-gray-400')
        if self._timestamp_label:
            self._timestamp_label.text = 'No data'
    
    def _update_element(self, data: Any) -> None:
        """Update element with new data"""
        # Data updates are handled by timer
        pass
    
    def cleanup(self) -> None:
        """Cleanup component"""
        if self._update_timer:
            self._update_timer.cancel()
        super().cleanup()

class DashboardComponent(BaseComponent):
    """Main dashboard component"""

    def __init__(self, config_service: ConfigurationService, sensor_manager: SensorManager, controller_manager: ControllerManager):
        config = ComponentConfig("dashboard")
        super().__init__(config)
        self.config_service = config_service
        self.sensor_manager = sensor_manager
        self.controller_manager = controller_manager
        self.component_registry = get_component_registry()
        self._sensor_cards: Dict[str, SensorCardComponent] = {}
        self._controller_cards: Dict[str, ui.card] = {}
        self._camera_stream: Optional[CameraStreamComponent] = None

        # Determine which sensors and controllers should be displayed
        self._dashboard_sensors = [sid for sid, cfg in self.config_service.get_sensor_configs() if cfg.get('show_on_dashboard')]
        self._dashboard_controllers = [cid for cid, cfg in self.config_service.get_controller_configs() if cfg.get('show_on_dashboard')]

    def render(self) -> ui.column:
        """Render dashboard"""
        with ui.column().classes('w-full') as dashboard:
            # Dashboard header
            ui.label('CVD Tracker Dashboard').classes('text-2xl font-bold mb-4')
            
            # System status overview
            self._render_system_status()
            
            # Main content area with camera stream and sensor data
            with ui.row().classes('w-full gap-4'):
                # Camera stream section (left side)
                if self._should_show_camera():
                    with ui.column().classes('flex-1'):
                        ui.label('Camera Stream').classes('text-lg font-semibold mb-2')
                        self._render_camera_stream()

                # Sensor data section (right side)
                if self._dashboard_sensors:
                    with ui.column().classes('flex-1'):
                        ui.label('Sensor Data').classes('text-lg font-semibold mb-2')
                        with ui.row().classes('w-full gap-4 flex-wrap'):
                            self._render_sensor_cards()

                if self._dashboard_controllers:
                    with ui.column().classes('flex-1'):
                        ui.label('Controller States').classes('text-lg font-semibold mb-2')
                        with ui.row().classes('w-full gap-4 flex-wrap'):
                            self._render_controller_cards()
        
        return dashboard

    def _render_system_status(self) -> None:
        """Render system status overview"""
        with ui.card().classes('w-full p-4 mb-4 cvd-card'):
            ui.label('System Status').classes('text-lg font-semibold mb-2')

            with ui.column().classes('w-full gap-2'):
                active_sensors = self.sensor_manager.get_active_sensors()
                active_controllers = [cid for cid in self.controller_manager.list_controllers() if self.controller_manager.get_controller(cid).status == ControllerStatus.RUNNING]

                ui.label(f"Sensors running: {', '.join(active_sensors) if active_sensors else 'none'}").classes('text-sm')
                ui.label(f"Controllers running: {', '.join(active_controllers) if active_controllers else 'none'}").classes('text-sm')

    def _should_show_camera(self) -> bool:
        for cid in self._dashboard_controllers:
            cfg = next((c for c_id, c in self.config_service.get_controller_configs() if c_id == cid), None)
            if cfg and 'camera' in str(cfg.get('type', '')).lower():
                return True
        return False
    
    def _render_camera_stream(self) -> None:
        """Render camera stream component"""
        if not self._should_show_camera():
            return
        try:
            # Create camera stream component
            self._camera_stream = CameraStreamComponent(
                controller_manager=self.controller_manager,
                update_interval=1/15,  # 15 FPS for dashboard
                max_width=480,
                max_height=360,
                component_id="dashboard_camera_stream"
            )
            
            # Render the camera stream
            self._camera_stream.render()
            self.component_registry.register(self._camera_stream)
            
        except Exception as e:
            error(f"Error rendering camera stream: {e}")
            # Show error message instead
            with ui.card().classes('p-4 cvd-card'):
                with ui.column().classes('items-center'):
                    ui.icon('videocam_off', size='lg').classes('text-gray-400 mb-2')
                    ui.label('Camera Stream Unavailable').classes('text-gray-600')
                    ui.label(f'Error: {str(e)}').classes('text-xs text-red-500')
    
    def _render_sensor_cards(self) -> None:
        """Render sensor cards"""
        sensor_configs = self.config_service.get_sensor_configs()

        for sensor_id, sensor_config in sensor_configs:
            if not sensor_config.get('enabled', True):
                continue
            if self._dashboard_sensors and sensor_id not in self._dashboard_sensors:
                continue
            
            # Create sensor card config
            card_config = SensorCardConfig(
                sensor_id=sensor_id,
                title=sensor_config.get('display_name', sensor_id),
                unit=sensor_config.get('unit', '°C'),
                precision=sensor_config.get('precision', 1),
                warning_threshold=sensor_config.get('warning_threshold'),
                error_threshold=sensor_config.get('error_threshold')
            )
            
            # Create and render sensor card
            component_config = ComponentConfig(f"sensor_card_{sensor_id}")
            sensor_card = SensorCardComponent(component_config, card_config, self.sensor_manager)
            sensor_card.render()
            
            self._sensor_cards[sensor_id] = sensor_card

    def _render_controller_cards(self) -> None:
        for controller_id in self._dashboard_controllers:
            controller = self.controller_manager.get_controller(controller_id)
            if not controller:
                continue
            with ui.card().classes('p-4 cvd-card min-w-48') as card:
                ui.label(controller_id).classes('text-lg font-semibold mb-2')
                output = controller.get_output()
                ui.label(str(output) if output is not None else 'No output').classes('text-sm')
            self._controller_cards[controller_id] = card
    
    def _update_element(self, data: Any) -> None:
        """Update dashboard with new data"""
        # Individual sensor cards handle their own updates
        pass

    def cleanup(self) -> None:
        """Cleanup dashboard"""
        # Cleanup sensor cards
        for card in self._sensor_cards.values():
            card.cleanup()
        self._sensor_cards.clear()

        self._controller_cards.clear()

        # Cleanup camera stream
        if self._camera_stream:
            self._camera_stream.cleanup()
            self._camera_stream = None
        
        super().cleanup()
