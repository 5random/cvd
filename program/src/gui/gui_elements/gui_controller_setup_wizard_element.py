"""Setup wizard component using NiceGUI stepper for comprehensive controller configuration."""

from typing import Any, Optional, Callable, Dict, List
from nicegui import ui
from nicegui.element import Element
from nicegui import events

from src.gui.gui_tab_components.gui_tab_base_component import (
    BaseComponent,
    ComponentConfig,
)
from src.gui.gui_tab_components.gui_tab_sensors_component import SensorConfigDialog
from src.gui.gui_elements.gui_sensor_setup_wizard_element import SensorSetupWizardComponent
from src.data_handler.sources.sensor_source_manager import SensorManager
from src.controllers.controller_manager import ControllerManager
from src.utils.config_utils.config_service import ConfigurationService
from src.utils.log_utils.log_service import info, warning, error, debug


class ControllerSetupWizardComponent(BaseComponent):
    """Comprehensive 4-step controller setup wizard using NiceGUI stepper."""

    def __init__(
        self,
        config_service: ConfigurationService,
        controller_manager: ControllerManager,
        sensor_manager: SensorManager,
        on_close: Optional[Callable[[], None]] = None,
    ):
        config = ComponentConfig("controller_setup_wizard")
        super().__init__(config)
        self.config_service = config_service
        self.controller_manager = controller_manager
        self.sensor_manager = sensor_manager
        self.on_close = on_close

        self._dialog = None
        self._stepper = None
        
        # Wizard data
        self._wizard_data: Dict[str, Any] = {
            'controller_id': '',
            'name': '',
            'type': 'reactor_state',
            'enabled': True,
            'show_on_dashboard': True,
            'selected_sensors': [],
            'selected_webcam': None,
            'webcam_config': {},
            'parameters': {},
            'algorithms': [],
            'state_output': []
        }
        
        # UI elements for each step
        self._step1_elements: Dict[str, Element] = {}
        self._step2_elements: Dict[str, Element] = {}
        self._step3_elements: Dict[str, Element] = {}
        self._step4_elements: Dict[str, Element] = {}
        
        # Available controller types and their configurations
        self._controller_types: Dict[str, Dict[str, Any]] = {
            'reactor_state': {
                'name': 'Reactor State Controller',
                'description': 'Monitors reactor operational state from sensor data',
                'requires_sensors': True,
                'requires_webcam': False,
                'algorithms': ['reactor_status_detection'],
                'default_state_output': ['Reaktor fehler', 'Reaktor OK'],
                'parameters': {
                    'min_valid_sensors': {'type': 'int', 'default': 1, 'min': 1, 'max': 10, 'label': 'Min. Valid Sensors'},
                    'alarm_threshold_high': {'type': 'float', 'default': 80.0, 'min': 0, 'max': 200, 'label': 'High Alarm Threshold (°C)'},
                    'alarm_threshold_low': {'type': 'float', 'default': 10.0, 'min': -50, 'max': 100, 'label': 'Low Alarm Threshold (°C)'},
                    'state_change_delay_s': {'type': 'int', 'default': 5, 'min': 1, 'max': 60, 'label': 'State Change Delay (s)'}
                }
            },
            'motion_detection': {
                'name': 'Motion Detection Controller',
                'description': 'Detects motion using camera input',
                'requires_sensors': False,
                'requires_webcam': True,
                'algorithms': ['bubble_detection'],
                'default_state_output': ['Keine Bewegung erkannt', 'Bewegung erkannt'],
                'parameters': {
                    'sensitivity': {'type': 'float', 'default': 0.5, 'min': 0.1, 'max': 1.0, 'step': 0.1, 'label': 'Motion Sensitivity'},
                    'min_area': {'type': 'int', 'default': 500, 'min': 100, 'max': 5000, 'label': 'Min. Motion Area (pixels)'},
                    'background_learning_rate': {'type': 'float', 'default': 0.01, 'min': 0.001, 'max': 0.1, 'step': 0.001, 'label': 'Background Learning Rate'},
                    'noise_threshold': {'type': 'int', 'default': 25, 'min': 5, 'max': 100, 'label': 'Noise Threshold'}
                }
            },
            'camera': {
                'name': 'Camera Controller',
                'description': 'Controls camera capture and processing',
                'requires_sensors': False,
                'requires_webcam': True,
                'algorithms': [],
                'default_state_output': ['Kamera fehler', 'Kamera OK'],
                'parameters': {
                    'fps': {'type': 'int', 'default': 30, 'min': 1, 'max': 60, 'label': 'Frames per Second'},
                    'resolution_width': {'type': 'int', 'default': 640, 'min': 320, 'max': 1920, 'label': 'Resolution Width'},
                    'resolution_height': {'type': 'int', 'default': 480, 'min': 240, 'max': 1080, 'label': 'Resolution Height'},
                    'brightness': {'type': 'int', 'default': 128, 'min': 0, 'max': 255, 'label': 'Brightness'},
                    'contrast': {'type': 'int', 'default': 32, 'min': 0, 'max': 100, 'label': 'Contrast'},
                    'saturation': {'type': 'int', 'default': 64, 'min': 0, 'max': 100, 'label': 'Saturation'}
                }
            }
        }
        
        # Sensor wizard for creating new sensors
        self._sensor_wizard = SensorSetupWizardComponent(
            config_service, sensor_manager, self._refresh_sensor_list
        )

    def render(self) -> ui.column:
        """Render method required by BaseComponent."""
        with ui.column().classes("w-full") as container:
            ui.label("Controller Setup Wizard Component").classes("text-lg font-bold")
            ui.label("Use show_dialog() to display the wizard").classes("text-sm text-gray-500")
        return container

    def show_dialog(self) -> None:
        """Display the controller setup wizard in a dialog."""
        self._reset_wizard_data()
        
        with ui.dialog().props("persistent") as dialog:
            self._dialog = dialog
            with ui.card().classes("w-[900px] max-w-[95vw] h-[700px]"):
                with ui.column().classes("w-full h-full"):
                    # Header
                    with ui.row().classes("items-center justify-between w-full p-4 border-b"):
                        ui.label("Controller Setup Wizard").classes("text-xl font-bold")
                        ui.button(icon="close", on_click=self._close_dialog).props("flat round")
                    
                    # Stepper content
                    with ui.column().classes("flex-1 p-4"):
                        self._render_stepper()
                        
        dialog.open()

    def _reset_wizard_data(self) -> None:
        """Reset wizard data to defaults."""
        self._wizard_data = {
            'controller_id': self.config_service.generate_next_controller_id(),
            'name': '',
            'type': 'reactor_state',
            'enabled': True,
            'show_on_dashboard': True,
            'selected_sensors': [],
            'selected_webcam': None,
            'webcam_config': {
                'device_index': 0,
                'width': 640,
                'height': 480,
                'fps': 30,
                'brightness': 128,
                'contrast': 32,
                'saturation': 64
            },
            'parameters': {},
            'algorithms': [],
            'state_output': []
        }
        self._update_controller_defaults()

    def _update_controller_defaults(self) -> None:
        """Update defaults based on selected controller type."""
        controller_type = self._wizard_data['type']
        if controller_type in self._controller_types:
            config = self._controller_types[controller_type]
            self._wizard_data['algorithms'] = config['algorithms'].copy()
            self._wizard_data['state_output'] = config['default_state_output'].copy()
            
            # Set default parameters
            self._wizard_data['parameters'] = {}
            for param_name, param_config in config['parameters'].items():
                self._wizard_data['parameters'][param_name] = param_config['default']

    def _render_stepper(self) -> None:
        """Render the 4-step wizard stepper."""
        with ui.stepper().props("vertical") as stepper:
            self._stepper = stepper
            
            # Step 1: Basic Controller Information
            with ui.step("basic_info", title="Basic Information", icon="info"):
                self._render_step1()
                with ui.stepper_navigation():
                    ui.button("Next", on_click=self._validate_and_next_step1).props("color=primary")
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")
            
            # Step 2: Source Selection
            with ui.step("source_config", title="Source Selection", icon="input"):
                self._render_step2()
                with ui.stepper_navigation():
                    ui.button("Previous", on_click=self._stepper.previous)
                    ui.button("Next", on_click=self._validate_and_next_step2).props("color=primary")
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")
            
            # Step 3: Controller Settings
            with ui.step("settings", title="Controller Settings", icon="tune"):
                self._render_step3()
                with ui.stepper_navigation():
                    ui.button("Previous", on_click=self._stepper.previous)
                    ui.button("Next", on_click=self._stepper.next).props("color=primary")
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")
            
            # Step 4: Review and Confirmation
            with ui.step("review", title="Review & Confirm", icon="check_circle"):
                self._render_step4()
                with ui.stepper_navigation():
                    ui.button("Previous", on_click=self._stepper.previous)
                    ui.button("Create Controller", on_click=self._create_controller).props("color=positive")
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")

    def _render_step1(self) -> None:
        """Render step 1: Basic controller information."""
        ui.label("Configure basic controller information").classes("text-lg mb-4")
        
        with ui.column().classes("gap-4 w-full"):
            # Controller ID (auto-generated, not editable)
            with ui.row().classes("items-center gap-4"):
                ui.label("Controller ID:").classes("w-32 font-semibold")
                self._step1_elements['controller_id'] = ui.input(
                    value=self._wizard_data['controller_id']
                ).props("readonly outlined").classes("flex-1")
                ui.button(
                    icon="refresh", 
                    on_click=self._regenerate_controller_id
                ).props("flat").tooltip("Generate new ID")
            
            # Controller name
            with ui.row().classes("items-center gap-4"):
                ui.label("Display Name:").classes("w-32 font-semibold")
                self._step1_elements['name'] = ui.input(
                    placeholder="Enter controller display name"
                ).bind_value_to(self._wizard_data, 'name').props("outlined").classes("flex-1")
            
            # Controller type
            with ui.row().classes("items-center gap-4"):
                ui.label("Controller Type:").classes("w-32 font-semibold")
                self._step1_elements['type'] = ui.select(
                    list(self._controller_types.keys()),
                    value=self._wizard_data['type'],
                    on_change=self._on_controller_type_change
                ).bind_value_to(self._wizard_data, 'type').props("outlined").classes("flex-1")
            
            # Type description
            self._step1_elements['type_description'] = ui.label().classes("text-sm text-gray-600 ml-36")
            self._update_type_description()
            
            # Dashboard settings
            with ui.row().classes("items-center gap-4"):
                ui.label("Dashboard:").classes("w-32 font-semibold")
                self._step1_elements['show_on_dashboard'] = ui.checkbox(
                    "Show on Dashboard",
                    value=self._wizard_data['show_on_dashboard']
                ).bind_value_to(self._wizard_data, 'show_on_dashboard')

    def _render_step2(self) -> None:
        """Render step 2: Source selection."""
        ui.label("Select data sources for the controller").classes("text-lg mb-4")
        
        with ui.column().classes("gap-4 w-full"):
            # Sensor selection (if required by controller type)
            if self._controller_types[self._wizard_data['type']]['requires_sensors']:
                with ui.card().classes("w-full"):
                    with ui.card_section():
                        ui.label("Sensor Data Sources").classes("font-semibold mb-2")
                        
                        # Available sensors
                        self._step2_elements['sensor_container'] = ui.column().classes("gap-2")
                        self._refresh_sensor_list()
                        
                        # Add new sensor button
                        with ui.row().classes("gap-2 mt-2"):
                            ui.button(
                                "Add New Sensor",
                                on_click=self._show_sensor_wizard,
                                icon="add"
                            ).props("color=primary outlined")
            
            # Webcam selection (if required by controller type)
            if self._controller_types[self._wizard_data['type']]['requires_webcam']:
                with ui.card().classes("w-full"):
                    with ui.card_section():
                        ui.label("Webcam Configuration").classes("font-semibold mb-2")
                        
                        # Webcam selection
                        self._step2_elements['webcam_container'] = ui.column().classes("gap-4")
                        self._render_webcam_selection()

    def _render_step3(self) -> None:
        """Render step 3: Controller-specific settings."""
        ui.label("Configure controller-specific parameters").classes("text-lg mb-4")
        
        with ui.column().classes("gap-4 w-full"):
            # Controller parameters
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Controller Parameters").classes("font-semibold mb-2")
                    
                    self._step3_elements['parameters_container'] = ui.column().classes("gap-4")
                    self._render_controller_parameters()
            
            # State output configuration
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("State Output Messages").classes("font-semibold mb-2")
                    
                    self._step3_elements['state_container'] = ui.column().classes("gap-2")
                    self._render_state_output_config()

    def _render_step4(self) -> None:
        """Render step 4: Review and confirmation."""
        ui.label("Review controller configuration before creation").classes("text-lg mb-4")
        
        self._step4_elements['review_container'] = ui.column().classes("gap-4 w-full")
        self._update_review_display()

    def _regenerate_controller_id(self) -> None:
        """Generate a new controller ID."""
        new_id = self.config_service.generate_next_controller_id()
        self._wizard_data['controller_id'] = new_id
        if 'controller_id' in self._step1_elements:
            self._step1_elements['controller_id'].set_value(new_id)

    def _on_controller_type_change(self, e: events.ValueChangeEventArguments) -> None:
        """Handle controller type change."""
        self._update_controller_defaults()
        self._update_type_description()
        # Refresh step 2 and 3 if they exist
        if hasattr(self, '_step2_elements'):
            self._refresh_step2()
        if hasattr(self, '_step3_elements'):
            self._refresh_step3()

    def _update_type_description(self) -> None:
        """Update the controller type description."""
        if 'type_description' in self._step1_elements:
            controller_type = self._wizard_data['type']
            if controller_type in self._controller_types:
                description = self._controller_types[controller_type]['description']
                self._step1_elements['type_description'].set_text(description)

    def _refresh_sensor_list(self) -> None:
        """Refresh the list of available sensors."""
        if 'sensor_container' not in self._step2_elements:
            return
            
        container = self._step2_elements['sensor_container']
        container.clear()
        
        available_sensors = self.config_service.get_sensor_configs()
        
        if not available_sensors:
            with container:
                ui.label("No sensors configured. Create a sensor first.").classes("text-gray-500")
            return
        
        with container:
            for sensor_id, sensor_config in available_sensors:
                with ui.row().classes("items-center gap-2"):
                    checkbox = ui.checkbox(
                        f"{sensor_config.get('name', sensor_id)} ({sensor_id})",
                        value=sensor_id in self._wizard_data['selected_sensors'],
                        on_change=lambda e, sid=sensor_id: self._toggle_sensor_selection(sid, e.value)
                    )
                    ui.label(f"Type: {sensor_config.get('type', 'unknown')}").classes("text-sm text-gray-600")

    def _toggle_sensor_selection(self, sensor_id: str, selected: bool) -> None:
        """Toggle sensor selection."""
        if selected and sensor_id not in self._wizard_data['selected_sensors']:
            self._wizard_data['selected_sensors'].append(sensor_id)
        elif not selected and sensor_id in self._wizard_data['selected_sensors']:
            self._wizard_data['selected_sensors'].remove(sensor_id)

    def _show_sensor_wizard(self) -> None:
        """Show the sensor setup wizard."""
        self._sensor_wizard.show_dialog()

    def _render_webcam_selection(self) -> None:
        """Render webcam selection and configuration."""
        container = self._step2_elements['webcam_container']
        container.clear()
        
        with container:
            # Webcam selection
            with ui.row().classes("items-center gap-4"):
                ui.label("Webcam:").classes("w-32 font-semibold")
                webcam_options = self._get_available_webcams()
                self._step2_elements['webcam_select'] = ui.select(
                    webcam_options,
                    value=self._wizard_data['selected_webcam'],
                    on_change=self._on_webcam_change
                ).bind_value_to(self._wizard_data, 'selected_webcam').props("outlined").classes("flex-1")
            
            # Webcam configuration
            if self._wizard_data['selected_webcam']:
                ui.separator().classes("my-4")
                ui.label("Webcam Settings").classes("font-semibold mb-2")
                
                with ui.column().classes("gap-4"):
                    # Basic settings
                    with ui.row().classes("items-center gap-4"):
                        ui.label("Resolution:").classes("w-24")
                        ui.number(
                            label="Width", value=self._wizard_data['webcam_config']['width']
                        ).bind_value_to(self._wizard_data['webcam_config'], 'width').classes("w-24")
                        ui.label("x")
                        ui.number(
                            label="Height", value=self._wizard_data['webcam_config']['height']
                        ).bind_value_to(self._wizard_data['webcam_config'], 'height').classes("w-24")
                    
                    with ui.row().classes("items-center gap-4"):
                        ui.label("FPS:").classes("w-24")
                        ui.number(
                            value=self._wizard_data['webcam_config']['fps'], min=1, max=60
                        ).bind_value_to(self._wizard_data['webcam_config'], 'fps').classes("w-24")
                    
                    # Image settings
                    with ui.row().classes("items-center gap-4"):
                        ui.label("Brightness:").classes("w-24")
                        ui.slider(
                            min=0, max=255, value=self._wizard_data['webcam_config']['brightness']
                        ).bind_value_to(self._wizard_data['webcam_config'], 'brightness').classes("flex-1")
                    
                    with ui.row().classes("items-center gap-4"):
                        ui.label("Contrast:").classes("w-24")
                        ui.slider(
                            min=0, max=100, value=self._wizard_data['webcam_config']['contrast']
                        ).bind_value_to(self._wizard_data['webcam_config'], 'contrast').classes("flex-1")

    def _get_available_webcams(self) -> List[str]:
        """Get list of available webcams."""
        # This could be enhanced to detect actual webcams
        webcams = ["Built-in Camera", "USB Camera 1", "USB Camera 2", "Network Camera"]
        return webcams

    def _on_webcam_change(self, e: events.ValueChangeEventArguments) -> None:
        """Handle webcam selection change."""
        self._render_webcam_selection()

    def _render_controller_parameters(self) -> None:
        """Render controller-specific parameters."""
        container = self._step3_elements['parameters_container']
        container.clear()
        
        controller_type = self._wizard_data['type']
        if controller_type not in self._controller_types:
            return
        
        parameters = self._controller_types[controller_type]['parameters']
        
        with container:
            for param_name, param_config in parameters.items():
                with ui.row().classes("items-center gap-4"):
                    ui.label(f"{param_config['label']}:").classes("w-48 font-semibold")
                    
                    if param_config['type'] == 'int':
                        ui.number(
                            value=self._wizard_data['parameters'].get(param_name, param_config['default']),
                            min=param_config.get('min'),
                            max=param_config.get('max')
                        ).bind_value_to(self._wizard_data['parameters'], param_name).props("outlined").classes("flex-1")
                    elif param_config['type'] == 'float':
                        ui.number(
                            value=self._wizard_data['parameters'].get(param_name, param_config['default']),
                            min=param_config.get('min'),
                            max=param_config.get('max'),
                            step=param_config.get('step', 0.1)
                        ).bind_value_to(self._wizard_data['parameters'], param_name).props("outlined").classes("flex-1")

    def _update_state_message(self, index: int, value: str) -> None:
        """Update a specific state message."""
        if 0 <= index < len(self._wizard_data['state_output']):
            self._wizard_data['state_output'][index] = value

    def _render_state_output_config(self) -> None:
        """Render state output message configuration."""
        container = self._step3_elements['state_container']
        container.clear()
        
        with container:
            ui.label("Configure status messages for different controller states").classes("text-sm text-gray-600 mb-2")
            
            for i, message in enumerate(self._wizard_data['state_output']):
                with ui.row().classes("items-center gap-2"):
                    ui.label(f"State {i+1}:").classes("w-16")
                    message_input = ui.input(
                        value=message,
                        placeholder=f"Enter message for state {i+1}",
                        on_change=lambda e, idx=i: self._update_state_message(idx, e.value)
                    ).props("outlined").classes("flex-1")

    def _update_review_display(self) -> None:
        """Update the review display in step 4."""
        if 'review_container' not in self._step4_elements:
            return
            
        container = self._step4_elements['review_container']
        container.clear()
        
        with container:
            # Basic Information
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Basic Information").classes("text-lg font-semibold mb-2")
                    
                    with ui.column().classes("gap-1"):
                        ui.label(f"Controller ID: {self._wizard_data['controller_id']}").classes("font-mono")
                        ui.label(f"Name: {self._wizard_data['name'] or 'Not specified'}")
                        ui.label(f"Type: {self._controller_types[self._wizard_data['type']]['name']}")
                        ui.label(f"Show on Dashboard: {'Yes' if self._wizard_data['show_on_dashboard'] else 'No'}")
            
            # Data Sources
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Data Sources").classes("text-lg font-semibold mb-2")
                    
                    with ui.column().classes("gap-1"):
                        if self._wizard_data['selected_sensors']:
                            ui.label(f"Selected Sensors: {', '.join(self._wizard_data['selected_sensors'])}")
                        else:
                            ui.label("Selected Sensors: None")
                        
                        if self._wizard_data['selected_webcam']:
                            ui.label(f"Selected Webcam: {self._wizard_data['selected_webcam']}")
                            webcam_config = self._wizard_data['webcam_config']
                            ui.label(f"Resolution: {webcam_config['width']}x{webcam_config['height']} @ {webcam_config['fps']}fps")
                        else:
                            ui.label("Selected Webcam: None")
            
            # Controller Settings
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Controller Settings").classes("text-lg font-semibold mb-2")
                    
                    with ui.column().classes("gap-1"):
                        ui.label(f"Algorithms: {', '.join(self._wizard_data['algorithms']) if self._wizard_data['algorithms'] else 'None'}")
                        
                        if self._wizard_data['parameters']:
                            ui.label("Parameters:")
                            with ui.column().classes("gap-1 ml-4"):
                                for param_name, param_value in self._wizard_data['parameters'].items():
                                    ui.label(f"• {param_name}: {param_value}").classes("text-sm")
                        else:
                            ui.label("Parameters: Default values")
                        
                        ui.label(f"State Messages: {', '.join(self._wizard_data['state_output'])}")

    def _validate_and_next_step1(self) -> None:
        """Validate step 1 and proceed to next step."""
        errors = []
        
        if not self._wizard_data['controller_id']:
            errors.append("Controller ID is required")
            
        if not self._wizard_data['name']:
            errors.append("Controller name is required")
        
        if errors:
            ui.notify("; ".join(errors), color="negative")
            return
            
        if self._stepper:
            self._stepper.next()

    def _validate_and_next_step2(self) -> None:
        """Validate step 2 and proceed to next step."""
        errors = []
        controller_type = self._wizard_data['type']
        config = self._controller_types[controller_type]
        
        if config['requires_sensors'] and not self._wizard_data['selected_sensors']:
            errors.append("At least one sensor must be selected for this controller type")
            
        if config['requires_webcam'] and not self._wizard_data['selected_webcam']:
            errors.append("A webcam must be selected for this controller type")
        
        if errors:
            ui.notify("; ".join(errors), color="negative")
            return
            
        if self._stepper:
            self._stepper.next()

    def _create_controller(self) -> None:
        """Create the controller with the configured settings."""
        try:
            # Create controller configuration
            controller_config = {
                'name': self._wizard_data['name'],
                'type': self._wizard_data['type'],
                'enabled': self._wizard_data['enabled'],
                'show_on_dashboard': self._wizard_data['show_on_dashboard'],
                'algorithm': self._wizard_data['algorithms'],
                'state_output': self._wizard_data['state_output']
            }
            
            # Add type-specific configuration
            if self._wizard_data['type'] == 'motion_detection' and self._wizard_data['selected_webcam']:
                controller_config['parameters'] = {
                    'cam_id': self._wizard_data['selected_webcam'],
                    **self._wizard_data['parameters']
                }
                  # Add webcam configuration
                webcam_config = {
                    'webcam_id': self._wizard_data['selected_webcam'],
                    'name': self._wizard_data['selected_webcam'],
                    'device_index': self._wizard_data['webcam_config']['device_index'],
                    'resolution': [
                        self._wizard_data['webcam_config']['width'],
                        self._wizard_data['webcam_config']['height']
                    ],
                    'fps': self._wizard_data['webcam_config']['fps'],
                    'rotation': 0,
                    'uvc_settings': {
                        'brightness': self._wizard_data['webcam_config']['brightness'],
                        'contrast': self._wizard_data['webcam_config']['contrast'],
                        'saturation': self._wizard_data['webcam_config']['saturation']
                    }
                }
                  # Add webcam to hardware config
                try:
                    self.config_service.add_webcam_config(webcam_config)
                except Exception as e:
                    warning(f"Failed to add webcam configuration: {e}")
            
            elif self._wizard_data['type'] == 'reactor_state':
                controller_config['parameters'] = self._wizard_data['parameters']
                controller_config['input_sensors'] = self._wizard_data['selected_sensors']
            
            elif self._wizard_data['type'] == 'camera':
                controller_config['parameters'] = {
                    'cam_id': self._wizard_data['selected_webcam'],
                    **self._wizard_data['parameters']
                }
            
            # Add controller_id to controller config
            controller_config['controller_id'] = self._wizard_data['controller_id']
            
            # Validate and add controller configuration
            self.config_service._validate_controller_config(controller_config)
            self.config_service.add_controller_config(controller_config)
            
            info(f"Created controller configuration: {self._wizard_data['controller_id']}")
            ui.notify(f"Controller '{controller_config['name']}' created successfully!", color="positive")
            
            # Close dialog and notify parent
            self._close_dialog()
            
        except Exception as e:
            error(f"Failed to create controller: {e}")
            ui.notify(f"Failed to create controller: {str(e)}", color="negative")

    def _close_dialog(self) -> None:
        """Close the wizard dialog."""
        if self._dialog:
            self._dialog.close()
            self._dialog = None
            
        if self.on_close:
            self.on_close()

    def _refresh_step2(self) -> None:
        """Refresh step 2 elements."""
        if hasattr(self, '_step2_elements'):
            self._render_step2()

    def _refresh_step3(self) -> None:
        """Refresh step 3 elements."""
        if hasattr(self, '_step3_elements'):
            self._render_step3()

    def _update_element(self, data: Any) -> None:
        """Update element with new data (required by BaseComponent)."""
        pass


# Legacy compatibility class
class SetupWizardComponent(ControllerSetupWizardComponent):
    """Legacy compatibility wrapper for ControllerSetupWizardComponent."""
    
    def __init__(self, config_service, sensor_manager, controller_manager):
        super().__init__(config_service, controller_manager, sensor_manager)
        
    def close_dialog(self) -> None:
        """Close the setup wizard dialog if open."""
        if self._dialog:
            self._dialog.close()

    def _refresh_sensors(self) -> None:
        """Legacy method for compatibility."""
        self._refresh_sensor_list()

    def _refresh_controllers(self) -> None:
        """Legacy method - not applicable for controller wizard."""
        pass
        
    def show_dialog(
        self,
        start_step: str = "sensors",
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Display the setup wizard inside a dialog."""
        # For controller wizard, always start with controller setup
        super().show_dialog()
