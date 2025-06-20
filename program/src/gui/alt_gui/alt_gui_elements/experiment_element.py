from nicegui import ui
from datetime import datetime

class ExperimentManagementSection:
    def __init__(self, settings):
        """Initialize experiment management section with settings"""
        self.experiment_running = False
        settings = settings or {
            'experiment_name': f'Experiment_{datetime.now().strftime("%Y%m%d_%H%M")}',
            'duration': 60,  # Default duration in minutes
            'record_video': True,
            'record_motion_data': True,
            'record_timestamps': True,
            'save_alerts': False
        }
        self.settings = settings
        
        @ui.page('/experiment_management')
        def experiment_management_page():
            # Create the experiment management section
            self.create_experiment_section()

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