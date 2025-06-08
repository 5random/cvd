"""
Main web application class for managing the NiceGUI interface.
"""
import asyncio
import contextlib
import json
from typing import Optional

from nicegui import app, ui
import cv2
from src.controllers.controller_manager import create_cvd_controller_manager
from src.data_handler.sources.sensor_source_manager import SensorManager
from src.gui.gui_elements.gui_live_plot_element import (LivePlotComponent,
                                                        PlotConfig)
from src.gui.gui_elements.gui_notification_center_element import \
    create_notification_center
from src.gui.gui_tab_components.gui_tab_base_component import (
    ComponentRegistry, get_component_registry)
from src.gui.gui_tab_components.gui_tab_controllers_component import \
    ControllersComponent
from src.gui.gui_tab_components.gui_tab_dashboard_component import \
    DashboardComponent
from src.gui.gui_tab_components.gui_tab_data_component import \
    create_data_component
from src.gui.gui_tab_components.gui_tab_experiment_component import \
    create_experiment_component
from src.gui.gui_tab_components.gui_tab_log_component import LogComponent
from src.gui.gui_tab_components.gui_tab_sensors_component import (
    SensorsComponent,
    SensorConfigDialog,
    SensorInfo,
)
from src.gui.gui_tab_components.gui_setup_wizard_component import \
    SetupWizardComponent
from src.utils.config_utils.config_service import ConfigurationService, ConfigurationError
from src.utils.data_utils.data_manager import get_data_manager
from src.utils.log_utils.log_service import debug, error, info, warning
from src.gui.gui_elements.gui_webcam_stream_element import CameraStreamComponent
from starlette.staticfiles import StaticFiles


class WebApplication:
    """Main web application managing NiceGUI interface and routing"""
    def __init__(self, config_service: ConfigurationService, sensor_manager: SensorManager):
        self.config_service = config_service
        self.sensor_manager = sensor_manager
        # Initialize controller manager for dashboard and other components
        self.controller_manager = create_cvd_controller_manager()
        self.component_registry = get_component_registry()
        self._routes_registered = False

        # Initialize attributes that will be assigned later
        self._processing_task: Optional[asyncio.Task] = None
        self._title_label: Optional[ui.label] = None
        self._title_input: Optional[ui.input] = None
        self._refresh_rate_input: Optional[ui.number] = None
        self._sensors_component: Optional[SensorsComponent] = None
        self._controllers_component: Optional[ControllersComponent] = None
        self._log_component: Optional[LogComponent] = None
        self._sensor_readings_container: Optional[ui.column] = None
        self._live_plot: Optional[LivePlotComponent] = None
        self._sensor_list_container: Optional[ui.column] = None
        
        # Initialize notification center with error handling
        try:
            self._notification_center = create_notification_center(
                config_service=self.config_service,
                sensor_manager=self.sensor_manager,
                controller_manager=self.controller_manager,
                experiment_manager=None
            )
            # Register notification center for proper cleanup
            self.component_registry.register(self._notification_center)
        except Exception as e:
            error(f"Error initializing notification center: {e}")
            self._notification_center = None

        # sensor configuration UI state
        self._sensor_config_table: Optional[ui.table] = None
        self._sensor_config_dialog: Optional[SensorConfigDialog] = None
        self._selected_sensor_id: Optional[str] = None
    
    async def startup(self) -> None:
        """Async startup for web application"""
        info("Web application starting up...")
        # Apply persisted dark mode setting before starting controllers
        ui.dark_mode().value = self.config_service.get('ui.dark_mode', bool, True)
        await self.controller_manager.start_all_controllers()
        self._processing_task = asyncio.create_task(self._processing_loop())
        info("Web application startup complete")
    
    async def shutdown(self) -> None:
        """Async shutdown for web application"""
        info("Web application shutting down...")
        if hasattr(self, "_processing_task"):
            self._processing_task.cancel()
            with contextlib.suppress(Exception):
                await self._processing_task
        await self.controller_manager.stop_all_controllers()
        self.component_registry.cleanup_all()
        info("Web application shutdown complete")

    async def _processing_loop(self) -> None:
        while True:
            interval_ms = self.config_service.get(
                "controller_manager.processing_interval_ms", int, 30
            )
            interval = max(0.001, interval_ms / 1000.0)
            await self.sensor_manager.wait_for_new_data(timeout=interval)
            sensor_data = self.sensor_manager.get_latest_readings()
            await self.controller_manager.process_data(sensor_data)
    
    def register_components(self) -> None:
        """Register all UI components and routes with NiceGUI"""
        if self._routes_registered:
            warning("Routes already registered, skipping...")
            return
        
        self._setup_routes()
        self._setup_layout()
        self._routes_registered = True
        info("UI components and routes registered")
    
    def _setup_routes(self) -> None:
        """Setup web routes"""
        
        @ui.page('/')
        def index():
            """Main dashboard page"""
            return self._create_main_layout()
        
        @ui.page('/sensors')
        def sensors():
            """Sensor management page"""
            return self._create_sensor_page()
        
        @ui.page('/config')
        def config():
            """Configuration page"""
            return self._create_config_page()

        @ui.page('/setup')
        def setup():
            """Initial setup wizard"""
            return self._create_setup_wizard_page()
        
        @ui.page('/status')
        def status():
            """System status page"""
            return self._create_status_page()

        @ui.page('/video_feed')
        async def video_feed():
            """Stream MJPEG frames from the dashboard camera"""
            camera = self.component_registry.get_component('dashboard_camera_stream')

            async def gen():
                while True:
                    if isinstance(camera, CameraStreamComponent):
                        frame = camera.get_latest_frame()
                        if frame is not None:
                            success, buf = cv2.imencode('jpg', frame)
                            if success:
                                jpeg_bytes = buf.tobytes()
                                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                                       jpeg_bytes + b'\r\n')
                    await asyncio.sleep(camera.update_interval if isinstance(camera, CameraStreamComponent) else 0.03)

            return app.response_class(gen(), media_type='multipart/x-mixed-replace; boundary=frame')
    
    def _setup_layout(self) -> None:
        """Setup common layout elements"""
        # Add global CSS and JavaScript if needed
        ui.add_head_html('''
            <style>
                .cvd-header { background: linear-gradient(90deg, #1976d2, #1565c0); }
                .cvd-card { border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
                .cvd-sensor-value { font-size: 1.5rem; font-weight: bold; }
            </style>
        ''')
        # Serve download files directory via StaticFiles for generated packages
        
        dm = get_data_manager()
        if dm and dm.downloads_dir.exists():
            try:
                app.mount('/downloads', StaticFiles(directory=str(dm.downloads_dir)), name='downloads')
                debug(f"Mounted downloads directory at /downloads: {dm.downloads_dir}")
            except Exception as e:
                error(f"Error mounting downloads directory {dm.downloads_dir}: {e}")
    
    def _create_main_layout(self) -> None:
        """Create main dashboard layout"""
        # Header
        with ui.header().classes('cvd-header text-white'):
            with ui.row().classes('w-full items-center'):
                self._title_label = ui.label(
                    self.config_service.get('ui.title', str, 'CVD Tracker Dashboard')
                ).classes('text-h4 flex-grow')
                self._create_quick_settings()
                

        # Main content with tabs
        with ui.tabs().classes('w-full') as tabs:
            ui.tab('dashboard', label='Dashboard', icon='space_dashboard')
            ui.tab('sensors', label='Sensoren', icon='sensors')
            ui.tab('controllers', label='Controller', icon='speed')
            ui.tab('experiments', label='Experimente', icon='science')
            ui.tab('data', label='Daten', icon='folder')
            ui.tab('logs', label='Logs', icon='feed')
            ui.tab('settings', label='Einstellungen', icon='settings')
          # Tab panels
        with ui.tab_panels(tabs).classes('w-full h-full'):
            # Dashboard tab
            with ui.tab_panel('dashboard').classes('p-4'):
                self._create_dashboard_content()
            
            # Sensors tab
            with ui.tab_panel('sensors').classes('p-4'):
                self._sensors_component = SensorsComponent(self.sensor_manager, self.config_service)
                self.component_registry.register(self._sensors_component)
                self._sensors_component.render()
            
            # Controllers tab
            with ui.tab_panel('controllers').classes('p-4'):
                self._controllers_component = ControllersComponent(self.config_service, self.controller_manager)
                self.component_registry.register(self._controllers_component)
                self._controllers_component.render()
            
            # Experiments tab
            with ui.tab_panel('experiments').classes('p-4'):
                ui.label('Experiment Management').classes('text-xl mb-4')
                experiment_component = create_experiment_component(
                    component_id='experiment_component',
                    config_service=self.config_service,
                    sensor_manager=self.sensor_manager,
                    controller_manager=self.controller_manager
                )
                self.component_registry.register(experiment_component)
                experiment_component.render()

            # Data tab
            with ui.tab_panel('data').classes('p-4'):
                ui.label('Data Management').classes('text-xl mb-4')
                data_component = create_data_component(component_id='data_component')
                self.component_registry.register(data_component)
                data_component.render()
            
            # Logs tab
            with ui.tab_panel('logs').classes('p-4'):
                self._log_component = LogComponent()
                self.component_registry.register(self._log_component)
                self._log_component.render()
            
            # Settings tab
            with ui.tab_panel('settings').classes('p-4'):
                self._create_settings_content()
    
    def _create_dashboard_content(self) -> None:
        """Create dashboard tab content"""
        with ui.row().classes('w-full h-full gap-4'):
            # Left column - sensor dashboard
            dashboard_sensors = [sid for sid, cfg in self.config_service.get_sensor_configs() if cfg.get('show_on_dashboard')]

            with ui.column().classes('w-1/2'):
                dashboard = DashboardComponent(
                    self.config_service,
                    self.sensor_manager,
                    self.controller_manager
                )
                dashboard.render()

            # Right column - live plot
            if dashboard_sensors:
                with ui.column().classes('w-1/2'):
                    plot_config = PlotConfig(
                        max_points=2000,
                        refresh_rate_ms=1000,
                        history_seconds=3600
                    )
                    live_plot = LivePlotComponent(self.sensor_manager, plot_config, dashboard_sensors)
                    live_plot.render()
    
    def _create_sensors_content(self) -> None:
        """Create sensors tab content"""
        ui.label('Sensor Management').classes('text-xl mb-4')
        
        # Sensor status table
        with ui.card().classes('w-full p-4'):
            ui.label('Sensor Status').classes('text-lg font-semibold mb-2')
            
            # Get sensor status
            sensor_status = self.sensor_manager.get_sensor_status()
            
            if sensor_status:
                columns = [
                    {'name': 'sensor_id', 'label': 'Sensor ID', 'field': 'sensor_id'},
                    {'name': 'type', 'label': 'Type', 'field': 'sensor_type'},
                    {'name': 'connected', 'label': 'Connected', 'field': 'connected'},
                    {'name': 'polling', 'label': 'Polling', 'field': 'polling'},
                    {'name': 'status', 'label': 'Status', 'field': 'status'},
                    {'name': 'last_reading', 'label': 'Last Reading', 'field': 'last_reading'},
                ]
                
                rows = []
                for sensor_id, status in sensor_status.items():
                    rows.append({
                        'sensor_id': sensor_id,
                        'sensor_type': status.get('sensor_type', 'unknown'),
                        'connected': '✓' if status.get('connected', False) else '✗',
                        'polling': '✓' if status.get('polling', False) else '✗',
                        'status': status.get('status', 'unknown'),
                        'last_reading': status.get('last_reading', 'Never')
                    })
                
                ui.table(columns=columns, rows=rows).classes('w-full')
            else:
                ui.label('No sensors configured').classes('text-gray-500')
    
    def _create_settings_content(self) -> None:
        """Create settings tab content"""
        ui.label('System Settings').classes('text-xl mb-4')
        
        with ui.row().classes('w-full gap-4'):
            # Configuration section
            with ui.card().classes('w-1/2 p-4'):
                ui.label('Configuration').classes('text-lg font-semibold mb-2')
                
                # Basic settings
                self._title_input = ui.input(
                    label='System Title',
                    value=self.config_service.get('ui.title', str, 'CVD Tracker')
                )
                self._title_input.classes('w-full mb-2')

                self._refresh_rate_input = ui.number(
                    label='Refresh Rate (ms)',
                    value=self.config_service.get('ui.refresh_rate_ms', int, 1000),
                    min=100,
                    max=10000
                )
                self._refresh_rate_input.classes('w-full mb-2')
                
                ui.button('Save Settings', on_click=self._save_settings).classes('mt-4')
            
            # System status section
            with ui.card().classes('w-1/2 p-4'):
                ui.label('System Status').classes('text-lg font-semibold mb-2')
                
                # This is a simplified status display
                ui.label('✓ Configuration Service: Running').classes('text-green-600')
                ui.label('✓ Sensor Manager: Running').classes('text-green-600')
                ui.label('✓ Web Application: Running').classes('text-green-600')
    
    def _save_settings(self) -> None:
        """Persist settings from input fields to configuration"""
        try:
            if hasattr(self, '_title_input') and self._title_input is not None:
                self.config_service.set('ui.title', str(self._title_input.value))
                if hasattr(self, '_title_label') and self._title_label is not None:
                    self._title_label.text = str(self._title_input.value)

            if hasattr(self, '_refresh_rate_input') and self._refresh_rate_input is not None:
                self.config_service.set(
                    'ui.refresh_rate_ms', int(self._refresh_rate_input.value)
                )

            ui.notify('Settings saved successfully!', type='positive')
        except Exception as e:
            error(f'Error saving settings: {e}')
            ui.notify(f'Error saving settings: {e}', type='negative')
        
    def _create_quick_settings(self) -> None:
        """Create quick settings in header"""
        with ui.row().classes('gap-2'):
            # Dark mode toggle using NiceGUI's global dark mode object
            dark_mode = ui.dark_mode()

            def toggle_dark_mode() -> None:
                """Toggle UI dark mode and persist setting"""
                dark_mode.value = not dark_mode.value
                self.config_service.set('ui.dark_mode', dark_mode.value)

            ui.button(icon='dark_mode', color='#5898d4', on_click=toggle_dark_mode).props('flat round')
            
            # Refresh button
            ui.button(icon='refresh',color='#5898d4', on_click=ui.navigate.reload).props('flat round')
            
            # Full screen button
            ui.button(icon='fullscreen',color='#5898d4', on_click=lambda: ui.notify('Fullscreen mode')).props('flat round')
            # Notification center button
            # Only create notification button if attribute exists and not None
            if hasattr(self, '_notification_center') and self._notification_center is not None:
                self._notification_center.create_notification_button()
            else:
                debug('Notification center not initialized; skipping notification button')

    def _refresh_data(self) -> None:
        """Refresh all data"""
        ui.notify('Data refreshed')
        # Force update of all components
        # This would trigger component refresh in a real implementation
        self._create_dashboard_panel()
        self._create_sensors_panel()
        self._create_controllers_panel()
        self._create_experiments_panel()
        self._create_data_panel()
        self._create_logs_panel()
        self._create_settings_panel()
    
    def _create_dashboard_panel(self) -> None:
        """Create dashboard tab panel"""
        with ui.tab_panel('dashboard').classes('w-full h-full p-4'):
            ui.label('Dashboard').classes('text-h4 mb-4')
            
            with ui.row().classes('w-full gap-4'):
                # Sensor readings column
                with ui.column().classes('flex-1'):
                    self._create_sensor_readings_card()
                
                # Live plot column
                with ui.column().classes('flex-1'):
                    self._create_live_plot_card()
    
    def _create_sensors_panel(self) -> None:
        """Create sensors tab panel"""
        with ui.tab_panel('sensors').classes('w-full h-full p-4'):
            ui.label('Sensor Management').classes('text-h4 mb-4')
            
            with ui.row().classes('w-full gap-4'):
                # Sensor list
                with ui.column().classes('flex-1'):
                    self._create_sensor_list_card()
                
                # Sensor configuration
                with ui.column().classes('flex-1'):
                    self._create_sensor_config_card()
    
    def _create_controllers_panel(self) -> None:
        """Create controllers tab panel"""
        with ui.tab_panel('controllers').classes('w-full h-full p-4'):
            ui.label('Controller Management').classes('text-h4 mb-4')
            ui.label('Controller functionality will be implemented here').classes('text-body1')
    
    def _create_experiments_panel(self) -> None:
        """Create experiments tab panel"""
        with ui.tab_panel('experiments').classes('w-full h-full p-4'):
            ui.label('Experiment Management').classes('text-h4 mb-4')
            ui.label('Experiment functionality will be implemented here').classes('text-body1')
    
    def _create_data_panel(self) -> None:
        """Create data tab panel"""
        with ui.tab_panel('data').classes('w-full h-full p-4'):
            ui.label('Data Management').classes('text-h4 mb-4')
            ui.label('Data management functionality will be implemented here').classes('text-body1')
    
    def _create_logs_panel(self) -> None:
        """Create logs tab panel"""
        with ui.tab_panel('logs').classes('w-full h-full p-4'):
            ui.label('System Logs').classes('text-h4 mb-4')
            ui.label('Log viewing functionality will be implemented here').classes('text-body1')
    
    def _create_settings_panel(self) -> None:
        """Create settings tab panel"""
        with ui.tab_panel('settings').classes('w-full h-full p-4'):
            ui.label('System Settings').classes('text-h4 mb-4')
            
            with ui.card().classes('cvd-card w-full'):
                with ui.card_section():
                    ui.label('Configuration').classes('text-h6')
                
                with ui.card_section():
                    # Configuration editor
                    config_text = ui.textarea(
                        label='Configuration JSON',
                        value=self.config_service.get_raw_config_as_json()
                    ).classes('w-full h-64 font-mono')
                    
                    with ui.row():
                        ui.button('Save Configuration', 
                                 on_click=lambda: self._save_configuration(config_text.value))
                        ui.button('Reset to Defaults',
                                 on_click=lambda: self._reset_configuration(config_text))
    
    def _create_sensor_readings_card(self) -> None:
        """Create sensor readings display card"""
        with ui.card().classes('cvd-card w-full'):
            with ui.card_section():
                ui.label('Live Sensor Readings').classes('text-h6')
            
            with ui.card_section():
                # Create sensor readings display
                self._sensor_readings_container = ui.column().classes('w-full')
                
                # Timer to update readings
                ui.timer(1.0, self._update_sensor_readings)
    
    def _create_live_plot_card(self) -> None:
        """Create live plotting card"""
        with ui.card().classes('cvd-card w-full'):
            with ui.card_section():
                ui.label('Live Plot').classes('text-h6')

            with ui.card_section():
                # Build plot configuration from configuration values
                max_points = self.config_service.get('ui.liveplot.plot_max_points', int, 2000)
                history_seconds = self.config_service.get('ui.liveplot.history_seconds', int, 3600)
                sample_rate = self.config_service.get('ui.liveplot.sample_rate', int, 20)

                # Convert sample rate (Hz) to refresh interval in milliseconds
                refresh_rate_ms = int(1000 / sample_rate) if sample_rate > 0 else 1000

                plot_config = PlotConfig(
                    max_points=max_points,
                    refresh_rate_ms=refresh_rate_ms,
                    history_seconds=history_seconds,
                )

                # Instantiate live plot component and render
                self._live_plot = LivePlotComponent(self.sensor_manager, plot_config)
                self.component_registry.register(self._live_plot)
                self._live_plot.render()
    
    def _create_sensor_list_card(self) -> None:
        """Create sensor list card"""
        with ui.card().classes('cvd-card w-full'):
            with ui.card_section():
                ui.label('Active Sensors').classes('text-h6')
            
            with ui.card_section():
                self._sensor_list_container = ui.column().classes('w-full')
                self._update_sensor_list()
    
    def _create_sensor_config_card(self) -> None:
        """Create sensor configuration card"""
        with ui.card().classes('cvd-card w-full'):
            with ui.card_section():
                ui.label('Sensor Configuration').classes('text-h6')

                with ui.row().classes('gap-2'):
                    ui.button('Add Sensor', icon='add', on_click=self._add_sensor).props('color=primary')
                    ui.button('Edit Selected', icon='edit', on_click=self._edit_selected_sensor).props('color=secondary')
                    ui.button('Refresh', icon='refresh', on_click=self._load_sensor_configs).props('outline')

            with ui.card_section():
                columns = [
                    {'name': 'sensor_id', 'label': 'ID', 'field': 'sensor_id', 'align': 'left'},
                    {'name': 'name', 'label': 'Name', 'field': 'name', 'align': 'left'},
                    {'name': 'type', 'label': 'Type', 'field': 'type', 'align': 'left'},
                    {'name': 'interface', 'label': 'Interface', 'field': 'interface', 'align': 'left'},
                    {'name': 'port', 'label': 'Port', 'field': 'port', 'align': 'left'},
                    {'name': 'enabled', 'label': 'Enabled', 'field': 'enabled', 'align': 'center'},
                ]

                self._sensor_config_table = ui.table(
                    columns=columns,
                    rows=[],
                    row_key='sensor_id',
                    selection='single',
                    on_select=self._on_sensor_select,
                ).classes('w-full')

                # initialize dialog and load data
                if not self._sensor_config_dialog:
                    self._sensor_config_dialog = SensorConfigDialog(
                        self.config_service,
                        self.sensor_manager,
                        self._load_sensor_configs,
                    )

                self._load_sensor_configs()
    
    def _create_quick_settings_dropdown(self) -> None:
        """Create quick settings dropdown"""
        with ui.dropdown_button('Quick Settings', icon='settings').props('flat'):
            with ui.column():
                # Dark mode toggle
                dark_mode = ui.dark_mode()
                dark_mode.value = self.config_service.get('ui.dark_mode', bool, True)

                def on_dark_mode_change(e) -> None:
                    dark_mode.value = e.value
                    self.config_service.set('ui.dark_mode', dark_mode.value)

                ui.checkbox('Dark Mode', value=dark_mode.value, on_change=on_dark_mode_change)
                
                ui.separator()
                
                # Refresh rate setting
                refresh_rate = self.config_service.get('ui.refresh_rate_ms', int, 500)
                ui.number('Refresh Rate (ms)', value=refresh_rate, min=100, max=5000,
                         on_change=lambda e: self.config_service.set('ui.refresh_rate_ms', int(e.value)))
                
                ui.separator()

                # Fullscreen toggle
                fullscreen = ui.fullscreen()
                fullscreen.value = False
                ui.button('Toggle Fullscreen', on_click=lambda: fullscreen.toggle()).props('flat')

                ui.separator()

                # Reload button
                ui.button('Reload', on_click=ui.navigate.reload).props('flat')
                
                ui.separator()

                # Shutdown button
                ui.button('Shutdown', on_click=app.shutdown).props('flat')

                
    
    def _update_sensor_readings(self) -> None:
        """Update sensor readings display"""
        try:
            readings = self.sensor_manager.get_latest_readings()
            
            # Clear and rebuild readings display
            self._sensor_readings_container.clear()
            
            with self._sensor_readings_container:
                if not readings:
                    ui.label('No sensor data available').classes('text-body2 text-grey')
                    return
                
                for sensor_id, reading in readings.items():
                    with ui.row().classes('w-full items-center justify-between p-2 border rounded'):
                        ui.label(sensor_id).classes('text-body1')
                        
                        if reading.is_valid():
                            ui.label(f'{reading.value:.2f}°C').classes('cvd-sensor-value text-green')
                        else:
                            ui.label(f'Status: {reading.status.value}').classes('text-red')

        except Exception as e:
            error(f"Error updating sensor readings: {e}")
    
    def _update_sensor_list(self) -> None:
        """Update sensor list display"""
        try:
            sensor_status = self.sensor_manager.get_sensor_status()
            
            with self._sensor_list_container:
                if not sensor_status:
                    ui.label('No sensors configured').classes('text-body2 text-grey')
                    return
                
                for sensor_id, status in sensor_status.items():
                    with ui.row().classes('w-full items-center justify-between p-2 border rounded'):
                        with ui.column():
                            ui.label(sensor_id).classes('text-body1 font-bold')
                            ui.label(f"Type: {status['sensor_type']}").classes('text-body2')
                        
                        with ui.column():
                            status_color = 'green' if status['connected'] else 'red'
                            ui.badge('Connected' if status['connected'] else 'Disconnected').props(f'color={status_color}')
                            
                            if status['polling']:
                                ui.badge('Polling').props('color=blue')
        except Exception as e:
            error(f"Error updating sensor list: {e}")

    def _load_sensor_configs(self) -> None:
        """Load sensor configurations into table"""
        if not self._sensor_config_table:
            return
        try:
            configs = self.config_service.get_sensor_configs()
            rows = []
            for sid, cfg in configs:
                rows.append({
                    'sensor_id': sid,
                    'name': cfg.get('name', sid),
                    'type': cfg.get('type', 'unknown'),
                    'interface': cfg.get('interface', ''),
                    'port': cfg.get('port', ''),
                    'enabled': '✓' if cfg.get('enabled', True) else '✗',
                })
            self._sensor_config_table.rows.clear()
            self._sensor_config_table.rows.extend(rows)
        except Exception as e:
            error(f"Error loading sensor configs: {e}")

    def _on_sensor_select(self, event) -> None:
        """Handle table selection change"""
        try:
            selected = event.value
            self._selected_sensor_id = selected[0] if selected else None
        except Exception as e:
            error(f"Error selecting sensor: {e}")

    def _add_sensor(self) -> None:
        """Open dialog to add a new sensor"""
        if self._sensor_config_dialog:
            self._sensor_config_dialog.show_add_dialog()

    def _edit_selected_sensor(self) -> None:
        """Open dialog to edit the currently selected sensor"""
        if not self._selected_sensor_id:
            ui.notify('Please select a sensor to edit', color='warning')
            return

        configs = dict(self.config_service.get_sensor_configs())
        cfg = configs.get(self._selected_sensor_id)
        if not cfg:
            ui.notify('Sensor configuration not found', color='negative')
            return

        status = self.sensor_manager.get_sensor_status().get(self._selected_sensor_id, {})
        reading = self.sensor_manager.get_latest_readings().get(self._selected_sensor_id)

        sensor_info = SensorInfo(
            sensor_id=self._selected_sensor_id,
            name=cfg.get('name', self._selected_sensor_id),
            sensor_type=cfg.get('type', 'unknown'),
            source=cfg.get('source', 'unknown'),
            interface=cfg.get('interface', 'unknown'),
            port=cfg.get('port', ''),
            enabled=cfg.get('enabled', True),
            connected=status.get('connected', False),
            polling=status.get('polling', False),
            last_reading=status.get('last_reading'),
            status=status.get('status', 'unknown'),
            current_value=reading.value if reading else None,
            poll_interval_ms=cfg.get('poll_interval_ms', 1000),
            config=cfg,
        )

        if self._sensor_config_dialog:
            self._sensor_config_dialog.show_edit_dialog(sensor_info)
    
    def _save_configuration(self, config_json: str) -> None:
        """Save configuration from JSON text"""
        try:
            config_data = json.loads(config_json)
        except json.JSONDecodeError as e:
            ui.notify(f'Invalid configuration JSON: {e}', type='negative')
            return
        try:
            with open(self.config_service.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            self.config_service.reload()
        except (OSError, ConfigurationError) as e:
            ui.notify(f'Error saving configuration: {e}', type='negative')
        else:
            ui.notify('Configuration saved successfully', type='positive')
    
    def _reset_configuration(self, config_textarea) -> None:
        """Reset configuration to defaults"""
        try:
            self.config_service.reset_to_defaults()
            config_textarea.value = self.config_service.get_raw_config_as_json()
        except (OSError, ConfigurationError) as e:
            ui.notify(f'Error resetting configuration: {e}', type='negative')
        else:
            ui.notify('Configuration reset to defaults', type='positive')
    
    def _create_sensor_page(self) -> None:
        """Create standalone sensor management page"""
        ui.label('Sensor Management').classes('text-h4 mb-4')
        sensors_component = SensorsComponent(self.sensor_manager, self.config_service)
        self.component_registry.register(sensors_component)
        sensors_component.render()
    
    def _create_config_page(self) -> None:
        """Create standalone configuration page"""
        ui.label('Configuration').classes('text-h4 mb-4')
        # JSON editor for configuration
        config_textarea = ui.textarea(value=self.config_service.get_raw_config_as_json())
        config_textarea.classes('w-full h-64')
        with ui.row().classes('gap-2 mt-2'):
            ui.button('Save', on_click=lambda: self._save_configuration(config_textarea.value)).props('color=primary')
            ui.button('Reset', on_click=lambda: self._reset_configuration(config_textarea)).props('outline')

    def _create_setup_wizard_page(self) -> None:
        """Create setup wizard page"""
        ui.label('Setup Wizard').classes('text-h4 mb-4')
        wizard = SetupWizardComponent(
            self.config_service,
            self.sensor_manager,
            self.controller_manager,
        )
        self.component_registry.register(wizard)
        wizard.render()
    
    def _create_status_page(self) -> None:
        """Create system status page"""
        ui.label('System Status').classes('text-h4 mb-4')
        # Reuse dashboard content for status overview
        self._create_dashboard_content()
