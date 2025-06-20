#alternative gui application for the program that enables only basic functionality of the program those are:
# - live view of webcam with basic controls (start/stop webcam, adjust ROI, sensitivity settings, fps settings, resolution settings)
# - live status of motion detection algorithm applied to the webcam with ROI and sensitivity settings
# - email alert service for critical events (e.g. when motion is not detected) with alert delay settings (email alert shall include webcam image, motion detection status, timestamp, and other relevant information)
# - basic experiment management (start/stop experiment, view results/status, alert on critical events)

from nicegui import ui
from datetime import datetime
from typing import Optional, Dict, Any

from alt_gui import setup_global_styles
from alt_gui.alt_gui_elements.webcam_stream_element import WebcamStreamElement
from alt_gui.alt_gui_elements.alert_element import EmailAlertsSection
from alt_gui.alt_gui_elements.experiment_element import ExperimentManagementSection
from alt_gui.alt_gui_elements.motion_detection_element import MotionStatusSection

class SimpleGUIApplication:
    """Simple GUI application skeleton with basic CVD functionality"""
    
    def __init__(self):
        self.camera_active = False
        self.motion_detected = False
        self.experiment_running = False
        self.alerts_enabled = False
        # Placeholder settings
        self.settings = {
            'sensitivity': 50,
            'fps': 30,
            'resolution': '640x480 (30fps)',
            'roi_enabled': False,
            'email': '',
            'alert_delay': 5
        }
    
    def setup_global_styles(self):
        """Setup CSS styles matching the main application"""
        ui.add_head_html("""
            <style>
                .cvd-header { 
                    background: linear-gradient(90deg, #1976d2, #1565c0); 
                }
                .cvd-card { 
                    border-radius: 8px; 
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    padding: 16px;
                }
                .cvd-sensor-value { 
                    font-size: 1.5rem; 
                    font-weight: bold; 
                }
                .placeholder-content {
                    background: #f5f5f5;
                    border: 2px dashed #ccc;
                    border-radius: 8px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #666;
                    min-height: 200px;
                }
                /* Motion status indicators */
                .motion-detected {
                    color: #ff9800;
                    animation: pulse 2s infinite;
                }
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
                /* Card improvements */
                .cvd-card .q-expansion-item {
                    border: none;
                    box-shadow: none;
                }
                .cvd-card .q-expansion-item__container {
                    padding: 0;
                }
                /* Masonry layout improvements */
                .masonry-grid {
                    display: grid !important;
                    grid-template-columns: 2fr 1fr;
                    grid-template-rows: auto auto;
                    gap: 1rem;
                    grid-template-areas: 
                        "camera motion"
                        "experiment alerts";
                }
                /* Responsive adjustments */
                @media (max-width: 1024px) {
                    .masonry-grid {
                        grid-template-columns: 1fr !important;
                        grid-template-areas: 
                            "camera"
                            "motion"
                            "experiment" 
                            "alerts" !important;
                    }
                }
            </style>
        """)
        
    def create_camera_section(self):
        """Create camera control section"""
        with ui.card().classes('cvd-card w-full'):
            ui.label('Camera Control').classes('text-h6 mb-4')
            
            # Camera preview placeholder
            with ui.element('div').classes('placeholder-content mb-4'):
                ui.label('Camera Feed Preview')
            
            # Camera controls
            with ui.row().classes('w-full gap-4'):
                ui.button('Start Camera', on_click=self.toggle_camera).classes('flex-1')
                ui.button('Take Snapshot', on_click=lambda: ui.notify('Snapshot taken', type='info')).classes('flex-1')
            
            # Camera settings
            with ui.expansion('Camera Settings').classes('w-full mt-4'):
                with ui.column().classes('gap-4 p-4'):
                    # Sensitivity
                    ui.label('Motion Sensitivity')
                    ui.slider(min=0, max=100, value=self.settings['sensitivity'], 
                             on_change=self.update_sensitivity).classes('w-full')
                    
                    # FPS
                    ui.label('Frame Rate (FPS)')
                    ui.number(value=self.settings['fps'], on_change=self.update_fps).classes('w-full')
                    
                    # Resolution
                    ui.label('Resolution')
                    ui.select(['640x480 (30fps)', '1280x720 (30fps)', '1920x1080 (15fps)'], 
                             value=self.settings['resolution'], on_change=self.update_resolution).classes('w-full')
                    
                    # ROI
                    with ui.row().classes('w-full items-center'):
                        ui.switch('Enable ROI', on_change=lambda e: ui.notify('ROI toggled', type='info'))
                        ui.button('Set ROI', on_click=self.set_roi).props('outline')
    
    def create_motion_status_section(self):
        """Create motion detection status section"""
        with ui.card().classes('cvd-card w-full'):
            ui.label('Motion Detection').classes('text-h6 mb-4')
            
            # Motion status indicator
            with ui.row().classes('items-center gap-4 mb-4'):
                self.motion_indicator = ui.icon('motion_photos_on').classes(
                    'text-4xl motion-detected' if self.motion_detected else 'text-4xl text-gray-400')
                with ui.column():
                    ui.label('Motion Status').classes('text-caption')
                    self.motion_status_label = ui.label(
                        'Motion Detected' if self.motion_detected else 'No Motion').classes('cvd-sensor-value')
            
            # Motion statistics
            with ui.column().classes('gap-2 mt-4'):
                ui.label('Last Motion: Never').classes('text-body2')
                ui.label('Motion Events: 0').classes('text-body2')
                ui.label('Sensitivity: 50%').classes('text-body2')
    
    def create_experiment_section(self):
        """Create experiment management section"""
        with ui.card().classes('cvd-card w-full'):
            ui.label('Experiment Control').classes('text-h6 mb-4')
            
            # Experiment status
            with ui.row().classes('items-center gap-4 mb-4'):
                self.experiment_indicator = ui.icon('science').classes(
                    'text-4xl text-green-500' if self.experiment_running else 'text-4xl text-gray-400')
                with ui.column():
                    ui.label('Experiment Status').classes('text-caption')
                    self.experiment_status_label = ui.label(
                        'Running' if self.experiment_running else 'Stopped').classes('cvd-sensor-value')
            
            # Experiment controls
            with ui.row().classes('w-full gap-4 mt-4'):
                ui.button('Start Experiment', on_click=self.toggle_experiment).classes('flex-1')
                ui.button('View Results', on_click=lambda: ui.notify('Results viewed', type='info')).classes('flex-1')
    
    def create_email_alerts_section(self):
        """Create email alerts section"""
        with ui.card().classes('cvd-card w-full'):
            ui.label('Email Alerts').classes('text-h6 mb-4')
            
            # Alert status
            with ui.row().classes('items-center gap-4 mb-4'):
                self.alert_indicator = ui.icon('notifications').classes(
                    'text-4xl text-yellow-500' if self.alerts_enabled else 'text-4xl text-gray-400')
                with ui.column():
                    ui.label('Alert Status').classes('text-caption')
                    self.alert_status_label = ui.label(
                        'Enabled' if self.alerts_enabled else 'Disabled').classes('cvd-sensor-value')
            
            # Email settings
            with ui.expansion('Email Settings').classes('w-full mt-4'):
                with ui.column().classes('gap-4 p-4'):
                    ui.input('Email Address', value=self.settings['email']).classes('w-full')
                    ui.number('Alert Delay (minutes)', value=self.settings['alert_delay']).classes('w-full')
                    ui.switch('Enable Alerts', on_change=self.toggle_alerts)
            
            # Alert controls
            with ui.row().classes('w-full gap-4 mt-4'):
                ui.button('Send Test Alert', on_click=self.send_test_alert).classes('flex-1')
                ui.button('Alert History', on_click=self.show_alert_history).classes('flex-1')
        
    def create_header(self):
        """Create application header with status indicators"""
        with ui.header().classes('cvd-header text-white'):
            with ui.row().classes('w-full items-center justify-between px-4'):
                ui.label('CVD Tracker - Simple Monitor').classes('text-h4 flex-grow')
                
                # Status indicators
                with ui.row().classes('gap-4 items-center'):
                    # Camera status
                    self.camera_status_icon = ui.icon('videocam').classes(
                        'text-green-300' if self.camera_active else 'text-gray-400').tooltip('Camera Status')
                    
                    # Motion detection status
                    self.motion_status_icon = ui.icon('motion_photos_on').classes(
                        'text-orange-300' if self.motion_detected else 'text-gray-400').tooltip('Motion Detection Status')
                    
                    # Alert status
                    self.alert_status_icon = ui.icon('notifications').classes(
                        'text-yellow-300' if self.alerts_enabled else 'text-gray-400').tooltip('Email Alerts Status')
                      # Experiment status
                    self.experiment_status_icon = ui.icon('science').classes(
                        'text-green-300' if self.experiment_running else 'text-gray-400').tooltip('Experiment Status')
                    
                    # Separator
                    ui.separator().props('vertical inset').classes('bg-white opacity-30 mx-2')
                    
                    # Control buttons
                    ui.button(icon='fullscreen', on_click=lambda: ui.notify('function toggle_fullscreen not yet implemented', type='info')) \
                        .props('flat round').classes('text-white') \
                        .tooltip('Toggle Fullscreen')
                    
                    ui.button(icon='refresh', on_click=lambda: ui.notify('function reload_page not yet implemented', type='info')) \
                        .props('flat round').classes('text-white') \
                        .tooltip('Reload Page')
                    
                    # Dark/Light mode toggle
                    self.dark_mode_btn = ui.button(icon='dark_mode', on_click=lambda: ui.notify('function toggle_dark_mode not yet implemented', type='info')) \
                        .props('flat round').classes('text-white') \
                        .tooltip('Toggle Dark/Light Mode')
                    
                    # Separator
                    ui.separator().props('vertical inset').classes('bg-white opacity-30 mx-2')
                    
                    # Current time
                    self.time_label = ui.label('')
                    # schedule update_time every second
                    ui.timer(1.0, lambda: self.update_time())
    
    def create_main_layout(self):
        """Create the main application layout"""
        ui.page_title('CVD Tracker - Simple Monitor')
        
        # Setup global styles
        self.setup_global_styles()
        
        # Header
        self.create_header()
        # Main content area - Masonry-style layout with CSS Grid
        with ui.element('div').classes('w-full p-4 masonry-grid'):
            # Camera section (top-left, spans full height if needed)
            with ui.element('div').style('grid-area: camera;'):
                self.create_camera_section()
            
            # Motion Detection Status (top-right)
            with ui.element('div').style('grid-area: motion;'):
                self.create_motion_status_section()
            
            # Experiment Management (bottom-left)
            with ui.element('div').style('grid-area: experiment;'):
                self.create_experiment_section()
            
            # Email Alerts (bottom-right)
            with ui.element('div').style('grid-area: alerts;'):
                self.create_email_alerts_section()
            # Event handlers - placeholder implementations
    def update_time(self):
        """Update the time display in header"""
        self.time_label.text = datetime.now().strftime('%H:%M:%S')
    
    # Header button handlers - placeholder implementations
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        ui.notify('Toggle Fullscreen noch nicht implementiert', type='info')
    
    def reload_page(self):
        """Reload the current page"""
        ui.notify('Reload Page noch nicht implementiert', type='info')
    
    def toggle_dark_mode(self):
        """Toggle between dark and light mode"""
        ui.notify('Toggle Dark/Light Mode noch nicht implementiert', type='info')
    
    # Context menu handlers - all placeholder implementations
    def show_camera_settings_context(self):
        """Show camera settings from context menu"""
        ui.notify('Camera Settings (Rechtsklick) noch nicht implementiert', type='info')
    
    def start_recording_context(self):
        """Start recording from context menu"""
        ui.notify('Start Recording (Rechtsklick) noch nicht implementiert', type='info')
    
    def take_snapshot_context(self):
        """Take snapshot from context menu"""
        ui.notify('Take Snapshot (Rechtsklick) noch nicht implementiert', type='info')
    
    def adjust_roi_context(self):
        """Adjust ROI from context menu"""
        ui.notify('Adjust ROI (Rechtsklick) noch nicht implementiert', type='info')
    
    def reset_view_context(self):
        """Reset view from context menu"""
        ui.notify('Reset View (Rechtsklick) noch nicht implementiert', type='info')
    
    # Main event handlers - placeholder implementations  
    def toggle_camera(self):
        """Toggle camera on/off"""
        ui.notify('toggle_camera noch nicht implementiert', type='info')
    
    def update_sensitivity(self, e):
        """Update motion detection sensitivity"""
        ui.notify('update_sensitivity noch nicht implementiert', type='info')
    
    def update_fps(self, e):
        """Update camera FPS setting"""
        ui.notify('update_fps noch nicht implementiert', type='info')
    
    def update_resolution(self, e):
        """Update camera resolution setting"""
        ui.notify('update_resolution noch nicht implementiert', type='info')
    
    def set_roi(self):
        """Set region of interest"""
        ui.notify('set_roi noch nicht implementiert', type='info')
    
    def apply_camera_settings(self):
        """Apply all camera settings"""
        ui.notify('apply_camera_settings noch nicht implementiert', type='info')
    
    def toggle_alerts(self, e):
        """Toggle email alerts on/off"""
        ui.notify('toggle_alerts noch nicht implementiert', type='info')
    
    def send_test_alert(self):
        """Send a test email alert"""
        ui.notify('send_test_alert noch nicht implementiert', type='info')
    
    def show_alert_history(self):
        """Show alert history dialog"""
        ui.notify('show_alert_history noch nicht implementiert', type='info')    
    def toggle_experiment(self):
        """Toggle experiment running state"""
        ui.notify('toggle_experiment noch nicht implementiert', type='info')
    
    def run(self, host: str = 'localhost', port: int = 8081):
        """Run the simple GUI application"""
        @ui.page('/')
        def index():
            self.create_main_layout()
        
        print(f'Starting Simple CVD GUI on http://{host}:{port}')
        ui.run(
            host=host,
            port=port,
            title='CVD Tracker - Simple',
            favicon="https://www.tuhh.de/favicon.ico",
            dark=False,
            show=True
        )


# Entry point
def main():
    """Main entry point for the simple GUI application"""
    app = SimpleGUIApplication()
    app.run()


if __name__ in {"__main__", "__mp_main__"}:
    main()
