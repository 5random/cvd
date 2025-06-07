"""
Live plot component for real-time sensor data visualization.
"""
from typing import Dict, List, Any, Optional
from collections import deque
from dataclasses import dataclass
import time
from datetime import datetime
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from nicegui import ui

from src.data_handler.sources.sensor_source_manager import SensorManager
from src.data_handler.interface.sensor_interface import SensorReading, SensorStatus
from src.gui.gui_tab_components.gui_tab_base_component import BaseComponent, ComponentConfig
from src.utils.log_utils.log_service import info, warning, error, debug

@dataclass
class PlotConfig:
    """Configuration for live plot"""
    max_points: int = 2000
    refresh_rate_ms: int = 500
    history_seconds: int = 3600
    auto_scale: bool = True
    show_grid: bool = True
    line_width: int = 2

@dataclass
class SeriesConfig:
    """Configuration for individual data series"""
    sensor_id: str
    label: str
    color: str
    unit: str = "°C"
    y_axis: str = "y1"
    visible: bool = True

class LivePlotComponent(BaseComponent):
    """Live plotting component for sensor data"""

    def __init__(self, sensor_manager: SensorManager, plot_config: Optional[PlotConfig] = None, sensors_to_display: Optional[List[str]] = None):
        config = ComponentConfig(component_id="live_plot")
        super().__init__(config)
        self.sensor_manager = sensor_manager
        self.plot_config = plot_config or PlotConfig()
        self.sensors_to_display = sensors_to_display
        
        # Data storage
        self._data_store: Dict[str, deque] = {}
        # Calculate maxlen based on history window and refresh rate
        history_maxlen = max(
            1,
            int(self.plot_config.history_seconds * 1000 / self.plot_config.refresh_rate_ms),
        )
        self._time_store: deque = deque(maxlen=history_maxlen)
        self._series_configs: Dict[str, SeriesConfig] = {}
        
        # UI elements
        self._plot_element: Optional[ui.plotly] = None
        self._update_timer: Optional[ui.timer] = None
        self._control_panel: Optional[ui.row] = None
        
        # State
        self._is_running = True
        self._start_time = time.time()
    
    def render(self) -> ui.column:
        """Render live plot component"""
        with ui.column().classes('w-full h-full') as container:
            # Control panel
            self._render_control_panel()
            
            # Plot
            self._plot_element = ui.plotly(self._create_figure()).classes('w-full h-96')
            
            # Initialize data series
            self._initialize_series()
            
            # Start update timer
            self._update_timer = ui.timer(
                self.plot_config.refresh_rate_ms / 1000, 
                self._update_plot
            )
        
        return container
    
    def _render_control_panel(self) -> None:
        """Render plot control panel"""
        with ui.row().classes('w-full items-center gap-2 mb-2') as self._control_panel:
            ui.label('Live Plot').classes('text-lg font-semibold')
            
            # Play/pause button
            self._play_button = ui.button(
                icon='pause' if self._is_running else 'play_arrow',
                on_click=self._toggle_recording
            ).props('flat round')
            
            # Clear data button
            ui.button(
                icon='clear',
                on_click=self._clear_data
            ).props('flat round').tooltip('Clear data')
            
            # Settings button
            ui.button(
                icon='settings',
                on_click=self._show_settings
            ).props('flat round').tooltip('Plot settings')
            
            # Status indicator
            ui.space()
            status_color = 'green' if self._is_running else 'gray'
            ui.icon('fiber_manual_record', size='sm').classes(f'text-{status_color}-500')
            ui.label('Recording' if self._is_running else 'Paused').classes('text-sm')
    
    def _create_figure(self) -> go.Figure:
        """Create initial Plotly figure"""
        fig = go.Figure()
        
        # Configure layout
        # Determine y-axis title based on sensor units
        sensors = self.sensors_to_display if self.sensors_to_display is not None else self.sensor_manager.get_all_sensors()
        units = []
        for sensor_id in sensors:
            reading = self.sensor_manager.get_sensor_reading(sensor_id)
            if reading and reading.metadata:
                units.append(reading.metadata.get('unit', ''))

        first_unit = units[0] if units else ''
        unique_units = {u for u in units if u}
        if len(unique_units) == 1 and first_unit:
            yaxis_title = f"Value ({first_unit})"
        else:
            # Different units or unknown unit
            yaxis_title = "Value"

        fig.update_layout(
            title="Live Sensor Data",
            xaxis_title="Time",
            yaxis_title=yaxis_title,
            showlegend=True,
            height=400,
            margin=dict(l=50, r=50, t=50, b=50),
            paper_bgcolor='white',
            plot_bgcolor='white'
        )
        
        # Configure axes
        fig.update_layout(
            xaxis=dict(
                showgrid=self.plot_config.show_grid,
                gridcolor='lightgray',
                type='date'
            ),
            yaxis=dict(
                showgrid=self.plot_config.show_grid,
                gridcolor='lightgray',
                autorange=self.plot_config.auto_scale
            )
        )
        
        return fig
    
    def _initialize_series(self) -> None:
        """Initialize data series for all active sensors"""
        active_sensors = self.sensors_to_display if self.sensors_to_display is not None else self.sensor_manager.get_all_sensors()
        
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
        
        for i, sensor_id in enumerate(active_sensors):
            # Get sensor reading to determine unit
            reading = self.sensor_manager.get_sensor_reading(sensor_id)
            unit = "°C"  # Default unit
            
            if reading and reading.metadata:
                unit = reading.metadata.get('unit', '°C')
            
            # Create series config
            series_config = SeriesConfig(
                sensor_id=sensor_id,
                label=sensor_id.replace('_', ' ').title(),
                color=colors[i % len(colors)],
                unit=unit
            )
            
            self._series_configs[sensor_id] = series_config
            self._data_store[sensor_id] = deque(maxlen=self.plot_config.max_points)
    
    def _update_plot(self) -> None:
        """Update plot with latest sensor data"""
        if not self._is_running or not self._plot_element:
            return
        
        try:
            current_time = time.time()
            self._time_store.append(current_time)

            # Remove data older than history window
            cutoff = current_time - self.plot_config.history_seconds
            while self._time_store and self._time_store[0] < cutoff:
                self._time_store.popleft()
                for queue in self._data_store.values():
                    if queue:
                        queue.popleft()

            # Collect data from all sensors
            for sensor_id in self._series_configs:
                reading = self.sensor_manager.get_sensor_reading(sensor_id)
                
                if reading and reading.is_valid():
                    self._data_store[sensor_id].append(reading.value)
                else:
                    # Add None for missing data points
                    self._data_store[sensor_id].append(None)
            
            # Update plot
            self._refresh_plot()
            
        except Exception as e:
            error(f"Error updating live plot: {e}")
    
    def _refresh_plot(self) -> None:
        """Refresh the plot with current data"""
        if not self._plot_element:
            return
        
        # Convert stored timestamps to datetime objects for plotting
        time_axis = [datetime.fromtimestamp(ts) for ts in self._time_store]
        
        # Create traces for each sensor
        traces = []
        last_sensor_id = None
        for sensor_id, series_config in self._series_configs.items():
            last_sensor_id = sensor_id
            if not series_config.visible:
                continue

            data = list(self._data_store[sensor_id])

            if len(data) > 0:
                try:
                    trace = go.Scatter(
                        x=time_axis[:len(data)],
                        y=data,
                        mode='lines',
                        name=series_config.label,
                        line=dict(
                            color=series_config.color,
                            width=self.plot_config.line_width
                        ),
                        connectgaps=False,
                        hovertemplate=(
                            f"{series_config.label}: %{y:.2f}{series_config.unit}"
                            "<extra></extra>"
                        ),
                    )
                    traces.append(trace)
                except Exception as e:
                    error(
                        f"Error refreshing plot for sensor {sensor_id}: {e}",
                        exc_info=True,
                    )
        
        # Update plot
        try:
            self._plot_element.figure["data"] = traces
            # Update y-axis scaling based on configuration
            self._plot_element.figure.update_yaxes(autorange=self.plot_config.auto_scale)
            self._plot_element.update()
        except Exception as e:
            error(
                f"Error refreshing plot after sensor {last_sensor_id}: {e}",
                exc_info=True,
            )
    
    def _toggle_recording(self) -> None:
        """Toggle recording state"""
        self._is_running = not self._is_running
        
        if hasattr(self, '_play_button'):
            self._play_button.icon = 'pause' if self._is_running else 'play_arrow'
    
    def _clear_data(self) -> None:
        """Clear all plot data"""
        self._time_store.clear()
        for data_queue in self._data_store.values():
            data_queue.clear()
        
        if self._plot_element:
            self._plot_element.figure["data"] = []
            self._plot_element.update()
    
    def _show_settings(self) -> None:
        """Show plot settings dialog"""
        with ui.dialog() as dialog, ui.card():
            ui.label('Plot Settings').classes('text-lg font-semibold mb-4')
            
            with ui.column().classes('gap-4'):
                # Refresh rate
                ui.number(
                    label='Refresh Rate (ms)',
                    value=self.plot_config.refresh_rate_ms,
                    min=100,
                    max=5000,
                    step=100
                ).bind_value_to(self.plot_config, 'refresh_rate_ms')
                
                # Max points
                ui.number(
                    label='Max Data Points',
                    value=self.plot_config.max_points,
                    min=100,
                    max=10000,
                    step=100
                ).bind_value_to(self.plot_config, 'max_points')
                
                # Series visibility
                ui.label('Data Series').classes('font-semibold')
                for sensor_id, series_config in self._series_configs.items():
                    ui.checkbox(
                        text=series_config.label,
                        value=series_config.visible
                    ).bind_value_to(series_config, 'visible')
            
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Apply', on_click=lambda: self._apply_settings(dialog))
        
        dialog.open()
    
    def _apply_settings(self, dialog) -> None:
        """Apply settings changes"""
        # Update timer interval
        if self._update_timer:
            self._update_timer.interval = self.plot_config.refresh_rate_ms / 1000
        
        # Update data store max lengths
        for key, data_queue in list(self._data_store.items()):
            # Replace each queue with a new deque preserving existing data
            self._data_store[key] = deque(data_queue, maxlen=self.plot_config.max_points)

        history_maxlen = max(
            1,
            int(self.plot_config.history_seconds * 1000 / self.plot_config.refresh_rate_ms),
        )
        self._time_store = deque(self._time_store, maxlen=history_maxlen)

        dialog.close()
    
    def add_sensor(self, sensor_id: str, label: Optional[str] = None, color: Optional[str] = None) -> None:
        """Add a new sensor to the plot"""
        if sensor_id in self._series_configs:
            return
        
        series_config = SeriesConfig(
            sensor_id=sensor_id,
            label=label or sensor_id.replace('_', ' ').title(),
            color=color or '#1f77b4'
        )
        
        self._series_configs[sensor_id] = series_config
        self._data_store[sensor_id] = deque(maxlen=self.plot_config.max_points)
    
    def remove_sensor(self, sensor_id: str) -> None:
        """Remove a sensor from the plot"""
        if sensor_id in self._series_configs:
            del self._series_configs[sensor_id]
            del self._data_store[sensor_id]
    
    def _update_element(self, data: Any) -> None:
        """Update element with new data"""
        # Updates are handled by timer
        pass
    
    def cleanup(self) -> None:
        """Cleanup component"""
        if self._update_timer:
            self._update_timer.cancel()
        super().cleanup()
