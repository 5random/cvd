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
    
    def create_camera_section(self):
        """Create camera feed and controls section"""
        with ui.card().classes('cvd-card w-full'):
            ui.label('Live Camera Feed').classes('text-lg font-bold mb-2')
            
            # Video placeholder for camera stream with context menu
            with ui.row().classes('justify-center mb-4'):
                with ui.card().classes('border-2 border-dashed border-gray-300') \
                    .style('width: 640px; height: 480px; background-color: #f5f5f5; display: flex; align-items: center; justify-content: center;'):
                    
                    # Video element as placeholder for camera feed
                    self.video_element = ui.video(
                        'https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4'
                    ).style('width: 100%; height: 100%; object-fit: contain;')
                    
                    # Right-click context menu for camera
                    with ui.context_menu():
                        ui.menu_item('Camera Settings', on_click=lambda: ui.notify('function show_camera_settings_context not yet implemented', type='info'))
                        ui.separator()
                        ui.menu_item('Take Snapshot', on_click=lambda: ui.notify('function take_snapshot_context not yet implemented', type='info'))
                        ui.separator()
                        ui.menu_item('Adjust ROI', on_click=lambda: ui.notify('function adjust_roi_context not yet implemented', type='info'))
                        ui.menu_item('Reset View', on_click=lambda: ui.notify('function reset_view_context not yet implemented', type='info'))
            
            # Camera controls
            with ui.row().classes('gap-2 justify-center mb-4'):
                self.start_camera_btn = ui.button('Play Video', icon='play_arrow', on_click=self.toggle_video_play).props('color=positive')
                self.stop_camera_btn = ui.button('Pause Video', icon='pause', on_click=self.toggle_video_pause).props('color=negative')
              # Collapsible Camera Settings
            with ui.expansion('Camera Settings', icon='settings').classes('w-full mt-4'):
                with ui.column().classes('gap-4 w-full mt-2'):
                    # Basic Camera Settings
                    ui.label('Basic Settings').classes('text-base font-semibold text-blue-600')                    # Motion Sensitivity
                    ui.label('Motion Sensitivity').classes('text-sm font-medium text-gray-700')
                    with ui.row().classes('gap-3 items-center mb-3 w-full'):
                        self.sensitivity_number = ui.number(
                            value=self.settings['sensitivity'], min=0, max=100, step=1,
                            on_change=lambda value: ui.notify('function update_sensitivity not yet implemented', type='info')
                        ).classes('w-20').props('dense outlined')
                        self.sensitivity_slider = ui.slider(
                            min=0, max=100, value=self.settings['sensitivity'], step=1,
                            on_change=lambda value: ui.notify('function update_sensitivity not yet implemented', type='info')
                        ).props('thumb-label').classes('flex-1').style('min-width: 200px; height: 40px;')
                        
                        # Bind slider and number input values together
                        self.sensitivity_slider.bind_value(self.sensitivity_number, 'value')
                        self.sensitivity_number.bind_value(self.sensitivity_slider, 'value')
                        
                    # Frame Rate & Resolution
                    with ui.grid(columns=2).classes('gap-4 w-full mb-4'):
                        with ui.column():
                            ui.label('Frame Rate').classes('text-sm font-medium text-gray-700')
                            self.fps_select = ui.select(
                                [5, 10, 15, 20, 24, 30], label='FPS', value=self.settings['fps'],
                                on_change=lambda value: ui.notify('function update_fps not yet implemented', type='info')
                            ).classes('w-full').props('dense outlined')
                        
                        with ui.column():
                            ui.label('Resolution').classes('text-sm font-medium text-gray-700')
                            self.resolution_select = ui.select(
                                [
                                    '320x240 (30fps)', '352x288 (30fps)', '640x480 (30fps)', 
                                    '800x600 (30fps)', '1024x768 (30fps)', '1280x720 (30fps)', 
                                    '1280x960 (30fps)', '1280x1024 (30fps)', '1920x1080 (30fps)'
                                ], 
                                label='Resolution', value='640x480 (30fps)',
                                on_change=lambda value: ui.notify('function update_resolution not yet implemented', type='info')
                            ).classes('w-full').props('dense outlined')
                    
                    # Region of Interest
                    ui.label('Region of Interest').classes('text-sm font-medium text-gray-700')
                    with ui.row().classes('gap-2 mb-4'):
                        self.roi_checkbox = ui.checkbox('Enable ROI', value=self.settings['roi_enabled'])
                        ui.button('Set ROI', icon='crop_free', on_click=lambda: ui.notify('function set_roi not yet implemented', type='info')).props('size=sm')
                
                    # UVC Camera Controls Section
                    ui.separator().classes('my-4')
                    ui.label('UVC Camera Controls').classes('text-base font-semibold text-blue-600')
                    ui.label('Hardware-level camera adjustments').classes('text-xs text-gray-600 mb-3')
                    
                    # Image Quality Controls
                    ui.label('Image Quality').classes('text-sm font-medium text-gray-700 mb-2')                    # Brightness Control
                    ui.label('Brightness').classes('text-xs text-gray-600')
                    with ui.row().classes('gap-3 items-center mb-3 w-full'):
                        self.brightness_number = ui.number(
                            value=0, min=-100, max=100, step=1,
                            on_change=lambda value: ui.notify('function update_brightness not yet implemented', type='info')
                        ).classes('w-20').props('dense outlined')
                        self.brightness_slider = ui.slider(
                            min=-100, max=100, value=0, step=1,
                            on_change=lambda value: ui.notify('function update_brightness not yet implemented', type='info')
                        ).props('thumb-label').classes('flex-1').style('min-width: 200px; height: 40px;')
                        
                        # Bind values
                        self.brightness_slider.bind_value(self.brightness_number, 'value')
                        self.brightness_number.bind_value(self.brightness_slider, 'value')
                    
                    # Contrast Control
                    ui.label('Contrast').classes('text-xs text-gray-600')
                    with ui.row().classes('gap-3 items-center mb-3 w-full'):
                        self.contrast_number = ui.number(
                            value=100, min=0, max=200, step=1,
                            on_change=lambda value: ui.notify('function update_contrast not yet implemented', type='info')
                        ).classes('w-20').props('dense outlined')
                        self.contrast_slider = ui.slider(
                            min=0, max=200, value=100, step=1,
                            on_change=lambda value: ui.notify('function update_contrast not yet implemented', type='info')
                        ).props('thumb-label').classes('flex-1').style('min-width: 200px; height: 40px;')
                        
                        # Bind values
                        self.contrast_slider.bind_value(self.contrast_number, 'value')
                        self.contrast_number.bind_value(self.contrast_slider, 'value')
                    
                    # Saturation Control
                    ui.label('Saturation').classes('text-xs text-gray-600')
                    with ui.row().classes('gap-3 items-center mb-3 w-full'):
                        self.saturation_number = ui.number(
                            value=100, min=0, max=200, step=1,
                            on_change=lambda value: ui.notify('function update_saturation not yet implemented', type='info')
                        ).classes('w-20').props('dense outlined')
                        self.saturation_slider = ui.slider(
                            min=0, max=200, value=100, step=1,
                            on_change=lambda value: ui.notify('function update_saturation not yet implemented', type='info')
                        ).props('thumb-label').classes('flex-1').style('min-width: 200px; height: 40px;')
                        
                        # Bind values
                        self.saturation_slider.bind_value(self.saturation_number, 'value')
                        self.saturation_number.bind_value(self.saturation_slider, 'value')
                    
                    # Hue Control
                    ui.label('Hue').classes('text-xs text-gray-600')
                    with ui.row().classes('gap-3 items-center mb-3 w-full'):
                        self.hue_number = ui.number(
                            value=0, min=-180, max=180, step=1,
                            on_change=lambda value: ui.notify('function update_hue not yet implemented', type='info')
                        ).classes('w-20').props('dense outlined')
                        self.hue_slider = ui.slider(
                            min=-180, max=180, value=0, step=1,
                            on_change=lambda value: ui.notify('function update_hue not yet implemented', type='info')
                        ).props('thumb-label').classes('flex-1').style('min-width: 200px; height: 40px;')
                        
                        # Bind values
                        self.hue_slider.bind_value(self.hue_number, 'value')
                        self.hue_number.bind_value(self.hue_slider, 'value')
                    
                    # Sharpness Control
                    ui.label('Sharpness').classes('text-xs text-gray-600')
                    with ui.row().classes('gap-3 items-center mb-4 w-full'):
                        self.sharpness_number = ui.number(
                            value=50, min=0, max=100, step=1,
                            on_change=lambda value: ui.notify('function update_sharpness not yet implemented', type='info')
                        ).classes('w-20').props('dense outlined')
                        self.sharpness_slider = ui.slider(
                            min=0, max=100, value=50, step=1,
                            on_change=lambda value: ui.notify('function update_sharpness not yet implemented', type='info')
                        ).props('thumb-label').classes('flex-1').style('min-width: 200px; height: 40px;')
                        
                        # Bind values
                        self.sharpness_slider.bind_value(self.sharpness_number, 'value')
                        self.sharpness_number.bind_value(self.sharpness_slider, 'value')                    
                    # Exposure & Advanced Controls
                    ui.label('Exposure & Advanced').classes('text-sm font-medium text-gray-700 mb-2')
                    
                    # White Balance Control
                    ui.label('White Balance').classes('text-xs text-gray-600')
                    with ui.row().classes('gap-3 mb-3 items-center w-full'):
                        # Auto/manual toggle for white balance
                        self.wb_auto_checkbox = ui.checkbox(
                            'Auto', value=True,
                            on_change=self.toggle_white_balance_auto
                        ).classes('text-xs')
                        self.wb_manual_number = ui.number(
                            value=5000, min=2800, max=6500, step=100,
                            on_change=lambda value: ui.notify('function update_white_balance_manual not yet implemented', type='info')
                        ).classes('w-24').props('dense outlined')
                        self.wb_manual_slider = ui.slider(
                            min=2800, max=6500, value=5000, step=100,
                            on_change=lambda value: ui.notify('function update_white_balance_manual not yet implemented', type='info')
                        ).props('thumb-label').classes('flex-1').style('min-width: 200px; height: 40px;')
                        
                        # Initially disable manual controls since auto is enabled by default
                        self.wb_manual_number.disable()
                        self.wb_manual_slider.disable()
                        
                        # Bind values
                        self.wb_manual_slider.bind_value(self.wb_manual_number, 'value')
                        self.wb_manual_number.bind_value(self.wb_manual_slider, 'value')
                    
                    # Exposure Control
                    ui.label('Exposure').classes('text-xs text-gray-600')
                    with ui.row().classes('gap-3 mb-3 items-center w-full'):
                        # Auto/manual toggle for exposure
                        self.exposure_auto_checkbox = ui.checkbox(
                            'Auto', value=True,
                            on_change=self.toggle_exposure_auto
                        ).classes('text-xs')
                        self.exposure_manual_number = ui.number(
                            value=100, min=1, max=1000, step=1,
                            on_change=lambda value: ui.notify('function update_exposure_manual not yet implemented', type='info')
                        ).classes('w-24').props('dense outlined')
                        self.exposure_manual_slider = ui.slider(
                            min=1, max=1000, value=100, step=1,
                            on_change=lambda value: ui.notify('function update_exposure_manual not yet implemented', type='info')
                        ).props('thumb-label').classes('flex-1').style('min-width: 200px; height: 40px;')
                        
                        # note: on_change passed above in constructor

                        # Initially disable manual controls since auto is enabled by default
                        self.exposure_manual_number.disable()
                        self.exposure_manual_slider.disable()
                        # Bind values
                        self.exposure_manual_slider.bind_value(self.exposure_manual_number, 'value')
                        self.exposure_manual_number.bind_value(self.exposure_manual_slider, 'value')
                    
                    # Gain Control
                    ui.label('Gain').classes('text-xs text-gray-600')
                    with ui.row().classes('gap-3 items-center mb-3 w-full'):
                        self.gain_number = ui.number(
                            value=50, min=0, max=100, step=1,
                            on_change=lambda value: ui.notify('function update_gain not yet implemented', type='info')
                        ).classes('w-20').props('dense outlined')
                        self.gain_slider = ui.slider(
                            min=0, max=100, value=50, step=1,
                            on_change=lambda value: ui.notify('function update_gain not yet implemented', type='info')
                        ).props('thumb-label').classes('flex-1').style('min-width: 200px; height: 40px;')
                        
                        # Bind values
                        self.gain_slider.bind_value(self.gain_number, 'value')
                        self.gain_number.bind_value(self.gain_slider, 'value')
                    
                    # Gamma Control
                    ui.label('Gamma').classes('text-xs text-gray-600')
                    with ui.row().classes('gap-3 items-center mb-3 w-full'):
                        self.gamma_number = ui.number(
                            value=100, min=50, max=300, step=1,
                            on_change=lambda value: ui.notify('function update_gamma not yet implemented', type='info')
                        ).classes('w-20').props('dense outlined')
                        self.gamma_slider = ui.slider(
                            min=50, max=300, value=100, step=1,
                            on_change=lambda value: ui.notify('function update_gamma not yet implemented', type='info')
                        ).props('thumb-label').classes('flex-1').style('min-width: 200px; height: 40px;')
                        
                        # Bind values
                        self.gamma_slider.bind_value(self.gamma_number, 'value')
                        self.gamma_number.bind_value(self.gamma_slider, 'value')
                    
                    # Backlight Compensation Control
                    ui.label('Backlight Compensation').classes('text-xs text-gray-600')
                    with ui.row().classes('gap-3 items-center mb-4 w-full'):
                        self.backlight_comp_number = ui.number(
                            value=0, min=0, max=100, step=1,
                            on_change=lambda value: ui.notify('function update_backlight_comp not yet implemented', type='info')
                        ).classes('w-20').props('dense outlined')
                        self.backlight_comp_slider = ui.slider(
                            min=0, max=100, value=0, step=1,
                            on_change=lambda value: ui.notify('function update_backlight_comp not yet implemented', type='info')
                        ).props('thumb-label').classes('flex-1').style('min-width: 200px; height: 40px;')
                        
                        # Bind values
                        self.backlight_comp_slider.bind_value(self.backlight_comp_number, 'value')
                        self.backlight_comp_number.bind_value(self.backlight_comp_slider, 'value')
                
                    # UVC Control Buttons
                    with ui.row().classes('gap-2 mt-4 justify-end'):
                        ui.button('Reset to Defaults', icon='restore', on_click=lambda: ui.notify('function reset_uvc_defaults not yet implemented', type='info')).props('size=sm color=orange')
                        ui.button('Apply UVC Settings', icon='check', on_click=lambda: ui.notify('function apply_uvc_settings not yet implemented', type='info')).props('size=sm')
    
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
                on_change=lambda value: ui.notify('function toggle_alerts not yet implemented', type='info')
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
                ui.button('Send Test Alert', icon='send', on_click=lambda: ui.notify('function send_test_alert not yet implemented', type='info')) \
                    .props('color=warning').classes('flex-1')
                ui.button('Alert History', icon='history', on_click=lambda: ui.notify('function show_alert_history not yet implemented', type='info')) \
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
                    value=60, min=1, max=100000
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
                    'Start Experiment', icon='play_arrow', on_click=lambda: ui.notify('function toggle_experiment not yet implemented', type='info')
                ).props('color=positive').classes('flex-1')
                
                self.stop_experiment_btn = ui.button(
                    'Stop Experiment', icon='stop', on_click=lambda: ui.notify('function toggle_experiment not yet implemented', type='info')
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
    
    def toggle_video_play(self):
        """Play the video placeholder"""
        if hasattr(self, 'video_element'):
            self.video_element.play()
            # Update button states
            self.start_camera_btn.props('disable')
            self.stop_camera_btn.props(remove='disable')
        ui.notify('Video started', type='positive')
    
    def toggle_video_pause(self):
        """Pause the video placeholder"""
        if hasattr(self, 'video_element'):
            self.video_element.pause()
            # Update button states
            self.stop_camera_btn.props('disable')
            self.start_camera_btn.props(remove='disable')
        ui.notify('Video paused', type='info')
    
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
    
    def toggle_white_balance_auto(self, value):
        """Toggle white balance between auto and manual mode"""
        if value:
            # Auto mode - disable manual controls
            self.wb_manual_number.disable()
            self.wb_manual_slider.disable()
        else:
            # Manual mode - enable manual controls
            self.wb_manual_number.enable()
            self.wb_manual_slider.enable()
        ui.notify(f'White Balance set to {"Auto" if value else "Manual"}', type='info')
    
    def toggle_exposure_auto(self, value):
        """Toggle exposure between auto and manual mode"""
        if value:
            # Auto mode - disable manual controls
            self.exposure_manual_number.disable()
            self.exposure_manual_slider.disable()
        else:
            # Manual mode - enable manual controls
            self.exposure_manual_number.enable()
            self.exposure_manual_slider.enable()
        ui.notify(f'Exposure set to {"Auto" if value else "Manual"}', type='info')
    
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
