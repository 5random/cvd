#alternative gui application for the program that enables only basic functionality of the program those are:
# - live view of webcam with basic controls (start/stop webcam, adjust ROI, sensitivity settings, fps settings, resolution settings)
# - live status of motion detection algorithm applied to the webcam with ROI and sensitivity settings
# - email alert service for critical events (e.g. when motion is not detected) with alert delay settings (email alert shall include webcam image, motion detection status, timestamp, and other relevant information)
# - basic experiment management (start/stop experiment, view results/status, alert on critical events)

from nicegui import ui
from datetime import datetime
from typing import Optional, Dict, Any


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
            'resolution': '640x480',
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
                        'text-green-300' if self.camera_active else 'text-gray-400'
                    ).tooltip('Camera Status')
                    
                    # Motion detection status
                    self.motion_status_icon = ui.icon('motion_photos_on').classes(
                        'text-orange-300' if self.motion_detected else 'text-gray-400'
                    ).tooltip('Motion Detection Status')
                    
                    # Alert status
                    self.alert_status_icon = ui.icon('notifications').classes(
                        'text-yellow-300' if self.alerts_enabled else 'text-gray-400'
                    ).tooltip('Email Alerts Status')
                    
                    # Experiment status
                    self.experiment_status_icon = ui.icon('science').classes(
                        'text-green-300' if self.experiment_running else 'text-gray-400'
                    ).tooltip('Experiment Status')
                    
                    # Current time
                    self.time_label = ui.label('')
                    ui.timer(1.0, self.update_time)
    
    def create_camera_section(self):
        """Create camera feed and controls section"""
        with ui.card().classes('cvd-card w-full'):
            ui.label('Live Camera Feed').classes('text-lg font-bold mb-2')
            
            # Placeholder for camera stream with context menu
            with ui.row().classes('justify-center mb-4'):
                with ui.card().classes('border-2 border-dashed border-gray-300') \
                    .style('width: 640px; height: 480px; background-color: #f5f5f5; display: flex; align-items: center; justify-content: center;'):
                    ui.label('Camera Feed Placeholder').classes('text-gray-500 text-center')
                    
                    # Right-click context menu for camera
                    with ui.context_menu():
                        ui.menu_item('Camera Settings', on_click=self.show_camera_settings_context)
                        ui.separator()
                        ui.menu_item('Start Recording', on_click=self.start_recording_context)
                        ui.menu_item('Take Snapshot', on_click=self.take_snapshot_context)
                        ui.separator()
                        ui.menu_item('Adjust ROI', on_click=self.adjust_roi_context)
                        ui.menu_item('Reset View', on_click=self.reset_view_context)
            
            # Camera controls
            with ui.row().classes('gap-2 justify-center mb-4'):
                self.start_camera_btn = ui.button('Start Camera', icon='play_arrow', 
                                                 on_click=self.toggle_camera).props('color=positive')
                self.stop_camera_btn = ui.button('Stop Camera', icon='stop', 
                                                on_click=self.toggle_camera).props('color=negative')
                self.stop_camera_btn.disable()
            
            # Collapsible Camera Settings
            with ui.expansion('Camera Settings', icon='settings').classes('w-full mt-4'):
                with ui.grid(columns=2).classes('gap-4 w-full mt-2'):
                    # Left column - Basic settings
                    with ui.column():
                        ui.label('Motion Sensitivity').classes('text-sm font-medium')
                        self.sensitivity_slider = ui.slider(
                            min=0, max=100, value=self.settings['sensitivity'], step=1,
                            on_change=self.update_sensitivity
                        ).props('label-always')
                        
                        ui.label('Frame Rate').classes('text-sm font-medium')
                        self.fps_select = ui.select(
                            [15, 30, 60], label='FPS', value=self.settings['fps'],
                            on_change=self.update_fps
                        ).classes('w-full')
                    
                    # Right column - Advanced settings
                    with ui.column():
                        ui.label('Resolution').classes('text-sm font-medium')
                        self.resolution_select = ui.select(
                            ['640x480', '1280x720', '1920x1080'], 
                            label='Resolution', value=self.settings['resolution'],
                            on_change=self.update_resolution
                        ).classes('w-full')
                        
                        ui.label('Region of Interest').classes('text-sm font-medium')
                        with ui.row().classes('gap-2'):
                            self.roi_checkbox = ui.checkbox('Enable ROI', value=self.settings['roi_enabled'])
                            ui.button('Set ROI', icon='crop_free', on_click=self.set_roi).props('size=sm')
                
                # Apply settings button
                ui.button('Apply Settings', icon='check', on_click=self.apply_camera_settings) \
                    .props('color=primary').classes('w-full mt-4')
    
    def create_motion_status_section(self):
        """Create motion detection status section"""
        with ui.card().classes('cvd-card w-full'):
            ui.label('Motion Detection Status').classes('text-lg font-bold mb-2')
            
            # Main status display
            with ui.row().classes('items-center gap-4 mb-4'):
                self.motion_icon = ui.icon('motion_photos_off', size='3rem').classes('text-gray-500')
                with ui.column():
                    self.motion_label = ui.label('No Motion Detected').classes('text-lg font-semibold')
                    self.motion_percentage = ui.label('Motion Level: 0%').classes('cvd-sensor-value text-gray-600')
            
            # Status details
            with ui.grid(columns=3).classes('gap-4 w-full'):
                # Detection info
                with ui.column():
                    ui.label('Detection Info').classes('text-sm font-semibold text-gray-700')
                    self.confidence_label = ui.label('Confidence: --').classes('text-sm')
                    self.threshold_label = ui.label('Threshold: 50%').classes('text-sm')
                    self.roi_status_label = ui.label('ROI: Full Frame').classes('text-sm')
                
                # Timing info
                with ui.column():
                    ui.label('Timing').classes('text-sm font-semibold text-gray-700')
                    self.last_motion_label = ui.label('Last Motion: Never').classes('text-sm')
                    self.detection_count_label = ui.label('Detections: 0').classes('text-sm')
                    self.uptime_label = ui.label('Monitoring: 00:00:00').classes('text-sm')
                
                # Performance info
                with ui.column():
                    ui.label('Performance').classes('text-sm font-semibold text-gray-700')
                    self.fps_actual_label = ui.label('Actual FPS: --').classes('text-sm')
                    self.processing_time_label = ui.label('Processing: -- ms').classes('text-sm')
                    self.cpu_usage_label = ui.label('CPU Usage: --%').classes('text-sm')
    
    def create_email_alerts_section(self):
        """Create email alerts configuration section"""
        with ui.card().classes('cvd-card w-full'):
            ui.label('Email Alerts').classes('text-lg font-bold mb-2')
            
            # Enable/disable alerts
            self.alerts_enabled_checkbox = ui.checkbox(
                'Enable Email Alerts', value=self.alerts_enabled,
                on_change=self.toggle_alerts
            ).classes('mb-3')
            
            # Email settings
            with ui.column().classes('gap-3'):
                self.email_input = ui.input(
                    'Alert Email Address', 
                    placeholder='user@example.com',
                    value=self.settings['email']
                ).classes('w-full')
                
                self.alert_delay_input = ui.number(
                    'Alert Delay (minutes)', 
                    value=self.settings['alert_delay'], 
                    min=1, max=60
                ).classes('w-full')
                
                ui.label('Send alert if no motion detected for this duration').classes('text-xs text-gray-600')
            
            # Alert conditions
            ui.separator().classes('my-3')
            ui.label('Alert Conditions').classes('text-sm font-semibold')
            
            with ui.column().classes('ml-4 gap-1'):
                self.no_motion_alert = ui.checkbox('No motion detected (extended period)', value=True)
                self.camera_offline_alert = ui.checkbox('Camera goes offline', value=True)
                self.system_error_alert = ui.checkbox('System errors occur', value=True)
                self.experiment_complete_alert = ui.checkbox('Experiment completes', value=False)
            
            # Test and status
            ui.separator().classes('my-3')
            with ui.row().classes('gap-2 w-full'):
                ui.button('Send Test Alert', icon='send', on_click=self.send_test_alert) \
                    .props('color=warning').classes('flex-1')
                ui.button('Alert History', icon='history', on_click=self.show_alert_history) \
                    .props('color=secondary outline').classes('flex-1')
            
            # Last alert status
            self.last_alert_label = ui.label('No alerts sent').classes('text-xs text-gray-600 mt-2')
    
    def create_experiment_section(self):
        """Create experiment management section"""
        with ui.card().classes('cvd-card w-full'):
            ui.label('Experiment Management').classes('text-lg font-bold mb-2')
            
            # Current experiment status
            with ui.row().classes('items-center gap-2 mb-3'):
                self.experiment_icon = ui.icon('science', size='sm').classes('text-gray-500')
                self.experiment_status_label = ui.label('No experiment running').classes('font-medium')
            
            # Experiment details (hidden when not running)
            self.experiment_details = ui.column().classes('gap-1 mb-3')
            with self.experiment_details:
                self.experiment_name_label = ui.label('').classes('text-sm')
                self.experiment_duration_label = ui.label('').classes('text-sm')
                self.experiment_elapsed_label = ui.label('').classes('text-sm')
                self.experiment_progress = ui.linear_progress(value=0).classes('w-full')
            self.experiment_details.set_visibility(False)
            
            # Quick experiment setup
            ui.label('Quick Experiment Setup').classes('text-sm font-semibold mb-2')
            
            with ui.column().classes('gap-3'):
                self.experiment_name_input = ui.input(
                    'Experiment Name', 
                    placeholder='Enter experiment name',
                    value=f'Experiment_{datetime.now().strftime("%Y%m%d_%H%M")}'
                ).classes('w-full')
                
                self.experiment_duration_input = ui.number(
                    'Duration (minutes)', 
                    value=30, min=1, max=1440
                ).classes('w-full')
                
                # Experiment options
                ui.label('Recording Options').classes('text-sm font-semibold')
                with ui.column().classes('ml-4 gap-1'):
                    self.record_video_checkbox = ui.checkbox('Record video feed', value=True)
                    self.record_motion_data_checkbox = ui.checkbox('Record motion detection data', value=True)
                    self.record_timestamps_checkbox = ui.checkbox('Record event timestamps', value=True)
                    self.save_alerts_checkbox = ui.checkbox('Save alert events', value=False)
            
            # Control buttons
            with ui.row().classes('gap-2 w-full mt-4'):
                self.start_experiment_btn = ui.button(
                    'Start Experiment', icon='play_arrow', on_click=self.toggle_experiment
                ).props('color=positive').classes('flex-1')
                
                self.stop_experiment_btn = ui.button(
                    'Stop Experiment', icon='stop', on_click=self.toggle_experiment
                ).props('color=negative').classes('flex-1')
                self.stop_experiment_btn.disable()
            
            # Recent experiments
            ui.separator().classes('my-3')
            with ui.expansion('Recent Experiments').classes('w-full'):
                ui.label('No recent experiments available').classes('text-sm text-gray-600')
    
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
                }                .cvd-card .q-expansion-item__container {
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
            favicon='🔬',
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
