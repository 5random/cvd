#alternative gui application for the program that enables only basic functionality of the program those are:
# - live view of webcam with basic controls (start/stop webcam, adjust ROI, sensitivity settings, fps settings, resolution settings)
# - live status of motion detection algorithm applied to the webcam with ROI and sensitivity settings
# - email alert service for critical events (e.g. when motion is not detected) with alert delay settings (email alert shall include webcam image, motion detection status, timestamp, and other relevant information)
# - basic experiment management (start/stop experiment, view results/status, alert on critical events)

from nicegui import ui
from datetime import datetime
from typing import Optional, Dict, Any

from .alt_gui import (
    setup_global_styles,
    WebcamStreamElement,
    EmailAlertsSection,
    ExperimentManagementSection,
    MotionStatusSection,
)

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
        
        # Setup global styles using shared theme
        setup_global_styles(self)

        # Header
        self.create_header()

        # Instantiate shared UI sections
        self.webcam_stream = WebcamStreamElement(self.settings)
        self.motion_section = MotionStatusSection(self.settings)
        self.experiment_section = ExperimentManagementSection(self.settings)
        self.alerts_section = EmailAlertsSection(self.settings)

        # Main content area - Masonry-style layout with CSS Grid
        with ui.element('div').classes('w-full p-4 masonry-grid'):
            # Camera section (top-left, spans full height if needed)
            with ui.element('div').style('grid-area: camera;'):
                self.webcam_stream.create_camera_section()

            # Motion Detection Status (top-right)
            with ui.element('div').style('grid-area: motion;'):
                self.motion_section.create_motion_status_section()

            # Experiment Management (bottom-left)
            with ui.element('div').style('grid-area: experiment;'):
                self.experiment_section.create_experiment_section()

            # Email Alerts (bottom-right)
            with ui.element('div').style('grid-area: alerts;'):
                self.alerts_section.create_email_alerts_section()
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
