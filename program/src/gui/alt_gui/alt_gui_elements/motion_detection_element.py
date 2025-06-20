from nicegui import ui

class MotionStatusSection:
    def __init__(self, settings):
        """Initialize motion status section with settings"""
        self.camera_active = False
        self.motion_detected = False
        settings = settings or {
            'motion_detected': False,
            'confidence': 0,
            'threshold': 50,
            'roi_status': 'Full Frame',
            'last_motion': 'Never',
            'no_motion_detections': 0,
            'uptime': '00:00:00',
            'fps_actual': '--',
            'processing_time': '-- ms',
            'cpu_usage': '--%'
        }
        self.settings = settings
    
        @ui.page('/motion_status')
        def motion_status_page():
            # Create the motion status section
            self.create_motion_status_section()

    """Class to create a motion detection status section in the UI"""
    def create_motion_status_section(self):
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
                    self.detection_count_label = ui.label('No Motion Detections: 0').classes('text-sm')
                    self.uptime_label = ui.label('Monitoring: 00:00:00').classes('text-sm')
                
                # Performance info
                with ui.column():
                    ui.label('Performance').classes('text-sm font-semibold text-gray-700')
                    self.fps_actual_label = ui.label('Actual FPS: --').classes('text-sm')
                    self.processing_time_label = ui.label('Processing: -- ms').classes('text-sm')
                    self.cpu_usage_label = ui.label('CPU Usage: --%').classes('text-sm')