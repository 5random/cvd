"""Setup wizard component using NiceGUI stepper for comprehensive experiment configuration."""

from typing import Any, Optional, Callable, Dict, List
from datetime import datetime
from pathlib import Path
from nicegui import ui
import json
from src.utils.ui_helpers import notify_later

from src.gui.gui_tab_components.gui_tab_base_component import (
    BaseComponent,
    ComponentConfig,
)
from .gui_wizard_mixin import WizardMixin
from src.experiment_handler.experiment_manager import (
    ExperimentManager, ExperimentConfig, ExperimentState, ExperimentPhase,
    get_experiment_manager
)
from src.data_handler.sources.sensor_source_manager import SensorManager
from src.controllers.controller_manager import ControllerManager
from program.src.utils.config_service import ConfigurationService
from program.src.utils.log_service import info, warning, error, debug


class ExperimentSetupWizardComponent(WizardMixin, BaseComponent):
    """Comprehensive 4-step experiment setup wizard using NiceGUI stepper."""

    def __init__(
        self,
        config_service: ConfigurationService,
        experiment_manager: Optional[ExperimentManager] = None,
        sensor_manager: Optional[SensorManager] = None,
        controller_manager: Optional[ControllerManager] = None,
        on_close: Optional[Callable[[], None]] = None,
    ):
        config = ComponentConfig("experiment_setup_wizard")
        super().__init__(config)
        self.config_service = config_service
        self.experiment_manager = experiment_manager or get_experiment_manager()
        self.sensor_manager = sensor_manager
        self.controller_manager = controller_manager
        self.on_close = on_close

        self._dialog = None
        self._stepper = None
        
        # Wizard data
        self._wizard_data = {
            # Basic information
            'experiment_id': '',
            'name': '',
            'description': '',
            'duration_enabled': False,
            'duration_minutes': None,
            
            # Data sources
            'auto_start_sensors': True,
            'auto_start_controllers': True,
            'sensor_ids': [],
            'controller_ids': [],
            
            # Experiment parameters
            'data_collection_interval_ms': 1000,
            'auto_compress': True,
            'custom_parameters': {},
            
            # Phase configuration (future enhancement)
            'phases': [],
            'script_path': None,
            
            # Advanced settings
            'enable_logging': True,
            'log_level': 'INFO',
            'enable_notifications': True,
            'auto_save_interval_minutes': 5
        }
        
        # UI elements for each step
        self._step1_elements = {}
        self._step2_elements = {}
        self._step3_elements = {}
        self._step4_elements = {}
        
        # Available sensors and controllers
        self._available_sensors: List[str] = []
        self._available_controllers: List[str] = []
        
        # Phase templates for future use
        self._phase_templates = {
            'Basic Data Collection': {
                'description': 'Simple continuous data collection',
                'phases': [
                    {'name': 'Collection', 'duration_minutes': None, 'parameters': {}}
                ]
            },
            'Thermal Cycling': {
                'description': 'Temperature cycling with heating/cooling phases',
                'phases': [
                    {'name': 'Heating', 'duration_minutes': 30, 'parameters': {'target_temp': 100}},
                    {'name': 'Hold', 'duration_minutes': 15, 'parameters': {'target_temp': 100}},
                    {'name': 'Cooling', 'duration_minutes': 45, 'parameters': {'target_temp': 25}}
                ]
            },
            'Process Monitoring': {
                'description': 'Monitor a process with initialization and cleanup',
                'phases': [
                    {'name': 'Initialization', 'duration_minutes': 5, 'parameters': {}},
                    {'name': 'Processing', 'duration_minutes': None, 'parameters': {}},
                    {'name': 'Cleanup', 'duration_minutes': 10, 'parameters': {}}
                ]
            }
        }

    def render(self) -> ui.column:
        """Render method required by BaseComponent."""
        with ui.column().classes("w-full") as container:
            ui.label("Experiment Setup Wizard Component").classes("text-lg font-bold")
            ui.label("Use show_dialog() to display the wizard").classes("text-sm text-gray-500")
        return container

    def show_dialog(self) -> None:
        """Display the experiment setup wizard in a dialog."""
        self._reset_wizard_data()
        self._load_available_sources()
        
        with ui.dialog().props("persistent") as dialog:
            self._dialog = dialog
            with ui.card().classes("w-[900px] max-w-[95vw] h-[700px]"):
                with ui.column().classes("w-full h-full"):
                    # Header
                    with ui.row().classes("items-center justify-between w-full p-4 border-b"):
                        ui.label("Experiment Setup Wizard").classes("text-xl font-bold")
                        ui.button(icon="close", on_click=self._close_dialog).props("flat round")
                    
                    # Stepper content
                    with ui.column().classes("flex-1 p-4"):
                        self._render_stepper()
                        
        dialog.open()

    def _reset_wizard_data(self) -> None:
        """Reset wizard data to defaults."""
        self._wizard_data = {
            'experiment_id': self._generate_experiment_id(),
            'name': '',
            'description': '',
            'duration_enabled': False,
            'duration_minutes': 60,
            'auto_start_sensors': True,
            'auto_start_controllers': True,
            'sensor_ids': [],
            'controller_ids': [],
            'data_collection_interval_ms': 1000,
            'auto_compress': True,
            'custom_parameters': {},
            'phases': [],
            'script_path': None,
            'enable_logging': True,
            'log_level': 'INFO',
            'enable_notifications': True,
            'auto_save_interval_minutes': 5
        }

    def _generate_experiment_id(self) -> str:
        """Generate a unique experiment ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"exp_{timestamp}"

    def _load_available_sources(self) -> None:
        """Load available sensors and controllers."""
        # Load sensors
        self._available_sensors = []
        if self.sensor_manager:
            try:
                sensor_configs = self.config_service.get_sensor_configs()
                self._available_sensors = [config[0] for config in sensor_configs]
            except Exception as e:
                warning(f"Failed to load sensor configs: {e}")
        
        # Load controllers
        self._available_controllers = []
        if self.controller_manager:
            try:
                controllers = self.controller_manager.list_controllers()
                self._available_controllers = list(controllers)
            except Exception as e:
                warning(f"Failed to load controller configs: {e}")

    def _render_stepper(self) -> None:
        """Render the 4-step wizard stepper."""
        with ui.stepper().props("vertical") as stepper:
            self._stepper = stepper
            
            # Step 1: Basic Experiment Information
            with ui.step("basic_info", title="Basic Information", icon="info"):
                self._render_step1()
                with ui.stepper_navigation():
                    ui.button("Next", on_click=self._validate_and_next_step1).props("color=primary")
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")
            
            # Step 2: Data Sources Selection
            with ui.step("data_sources", title="Data Sources", icon="sensors"):
                self._render_step2()
                with ui.stepper_navigation():
                    ui.button("Previous", on_click=self._stepper.previous)
                    ui.button("Next", on_click=self._stepper.next).props("color=primary")
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")
            
            # Step 3: Experiment Parameters
            with ui.step("parameters", title="Parameters", icon="tune"):
                self._render_step3()
                with ui.stepper_navigation():
                    ui.button("Previous", on_click=self._stepper.previous)
                    ui.button("Next", on_click=self._validate_and_next_step3).props("color=primary")
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")
            
            # Step 4: Review and Confirmation
            with ui.step("review", title="Review & Confirm", icon="check_circle"):
                self._render_step4()
                with ui.stepper_navigation():
                    ui.button("Previous", on_click=self._stepper.previous)
                    ui.button("Create Only", on_click=self._create_experiment).props("color=primary")
                    ui.button("Create & Start", on_click=self._create_and_start_experiment).props("color=positive")
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")

    def _render_step1(self) -> None:
        """Render step 1: Basic experiment information."""
        ui.label("Configure basic experiment information").classes("text-lg mb-4")
        
        with ui.column().classes("gap-4 w-full"):
            # Experiment ID (auto-generated, not editable)
            with ui.row().classes("items-center gap-4"):
                ui.label("Experiment ID:").classes("w-40 font-semibold")
                self._step1_elements['experiment_id'] = ui.input(
                    value=self._wizard_data['experiment_id']
                ).props("readonly outlined").classes("flex-1")
                ui.button(
                    icon="refresh", 
                    on_click=self._regenerate_experiment_id
                ).props("flat").tooltip("Generate new ID")
            
            # Experiment name
            with ui.row().classes("items-center gap-4"):
                ui.label("Experiment Name:").classes("w-40 font-semibold")
                self._step1_elements['name'] = ui.input(
                    placeholder="Enter descriptive experiment name"
                ).bind_value_to(self._wizard_data, 'name').props("outlined").classes("flex-1")
            
            # Description
            with ui.row().classes("items-start gap-4"):
                ui.label("Description:").classes("w-40 font-semibold pt-2")
                self._step1_elements['description'] = ui.textarea(
                    placeholder="Optional description of experiment purpose and goals"
                ).bind_value_to(self._wizard_data, 'description').props("outlined").classes("flex-1")
            
            # Duration settings
            ui.separator()
            ui.label("Duration Settings").classes("font-semibold text-lg mt-4 mb-2")
            
            self._step1_elements['duration_enabled'] = ui.checkbox(
                'Set maximum duration', 
                value=self._wizard_data['duration_enabled']
            ).bind_value_to(self._wizard_data, 'duration_enabled')
            
            with ui.row().classes("items-center gap-4") as duration_row:
                ui.label("Duration (minutes):").classes("w-40 font-semibold")
                self._step1_elements['duration_minutes'] = ui.number(
                    min=1, max=43200, step=1,
                    value=self._wizard_data['duration_minutes'],
                    placeholder="Leave empty for unlimited duration"
                ).bind_value_to(self._wizard_data, 'duration_minutes').props("outlined").classes("flex-1")

            # Bind duration input visibility to checkbox
            duration_row.bind_visibility_from(self._wizard_data, 'duration_enabled')

    def _render_step2(self) -> None:
        """Render step 2: Data sources selection."""
        ui.label("Select sensors and controllers for data collection").classes("text-lg mb-4")
        
        with ui.column().classes("gap-6 w-full"):
            # Sensor configuration
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Sensor Configuration").classes("font-semibold text-lg mb-4")
                    
                    self._step2_elements['auto_start_sensors'] = ui.checkbox(
                        'Auto-start sensors when experiment begins', 
                        value=self._wizard_data['auto_start_sensors']
                    ).bind_value_to(self._wizard_data, 'auto_start_sensors')
                    
                    if self._available_sensors:
                        ui.label("Select specific sensors (leave empty to use all configured sensors):").classes("mt-4 mb-2")
                        
                        with ui.column().classes("gap-2"):
                            for sensor_id in self._available_sensors:
                                checkbox = ui.checkbox(
                                    sensor_id, 
                                    value=sensor_id in self._wizard_data['sensor_ids']
                                )
                                checkbox.on('update:model-value', 
                                    lambda e, sid=sensor_id: self._toggle_sensor(sid, e.args[0]))
                    else:
                        ui.label('No sensors configured. You can add sensors later or create new ones using the sensor wizard.').classes('text-orange-600 mt-4')
                        
                        if self.sensor_manager:
                            ui.button(
                                'Open Sensor Wizard',
                                icon='add_circle',
                                on_click=self._open_sensor_wizard
                            ).props('color=primary').classes('mt-2')
            
            # Controller configuration
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Controller Configuration").classes("font-semibold text-lg mb-4")
                    
                    self._step2_elements['auto_start_controllers'] = ui.checkbox(
                        'Auto-start controllers when experiment begins', 
                        value=self._wizard_data['auto_start_controllers']
                    ).bind_value_to(self._wizard_data, 'auto_start_controllers')
                    
                    if self._available_controllers:
                        ui.label("Select specific controllers (leave empty to use all configured controllers):").classes("mt-4 mb-2")
                        
                        with ui.column().classes("gap-2"):
                            for controller_id in self._available_controllers:
                                checkbox = ui.checkbox(
                                    controller_id, 
                                    value=controller_id in self._wizard_data['controller_ids']
                                )
                                checkbox.on('update:model-value', 
                                    lambda e, cid=controller_id: self._toggle_controller(cid, e.args[0]))
                    else:
                        ui.label('No controllers configured. You can add controllers later.').classes('text-gray-500 mt-4')

    def _render_step3(self) -> None:
        """Render step 3: Experiment parameters and configuration."""
        ui.label("Configure experiment parameters and data collection settings").classes("text-lg mb-4")
        
        with ui.column().classes("gap-6 w-full"):
            # Data collection settings
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Data Collection Settings").classes("font-semibold text-lg mb-4")
                    
                    with ui.row().classes("items-center gap-4"):
                        ui.label("Collection Interval:").classes("w-40 font-semibold")
                        ui.number(
                            suffix="ms", min=100, max=60000, step=100,
                            value=self._wizard_data['data_collection_interval_ms']
                        ).bind_value_to(self._wizard_data, 'data_collection_interval_ms').props("outlined").classes("flex-1")
                    
                    with ui.row().classes("items-center gap-4 mt-4"):
                        ui.label("Auto-save Interval:").classes("w-40 font-semibold")
                        ui.number(
                            suffix="min", min=1, max=60, step=1,
                            value=self._wizard_data['auto_save_interval_minutes']
                        ).bind_value_to(self._wizard_data, 'auto_save_interval_minutes').props("outlined").classes("flex-1")
                    
                    ui.separator().classes("my-4")
                    
                    self._step3_elements['auto_compress'] = ui.checkbox(
                        'Auto-compress experiment results when complete', 
                        value=self._wizard_data['auto_compress']
                    ).bind_value_to(self._wizard_data, 'auto_compress')
            
            # Logging and monitoring settings
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Logging & Monitoring").classes("font-semibold text-lg mb-4")
                    
                    self._step3_elements['enable_logging'] = ui.checkbox(
                        'Enable detailed logging', 
                        value=self._wizard_data['enable_logging']
                    ).bind_value_to(self._wizard_data, 'enable_logging')
                    
                    with ui.row().classes("items-center gap-4 mt-4"):
                        ui.label("Log Level:").classes("w-40 font-semibold")
                        ui.select(
                            ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                            value=self._wizard_data['log_level']
                        ).bind_value_to(self._wizard_data, 'log_level').props("outlined").classes("flex-1")
                    
                    self._step3_elements['enable_notifications'] = ui.checkbox(
                        'Enable status notifications', 
                        value=self._wizard_data['enable_notifications']
                    ).bind_value_to(self._wizard_data, 'enable_notifications').classes("mt-4")
            
            # Advanced parameters
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Advanced Parameters").classes("font-semibold text-lg mb-4")
                    
                    ui.label("Custom parameters (JSON format, optional):").classes("mb-2")
                    self._step3_elements['custom_parameters'] = ui.textarea(
                        placeholder='{"parameter1": "value1", "parameter2": 123}'
                    ).props("outlined rows=3").classes("w-full")
                    
                    ui.label("Script path (optional, for future G-Code or Python script execution):").classes("mb-2 mt-4")
                    self._step3_elements['script_path'] = ui.input(
                        placeholder="Path to script file"
                    ).bind_value_to(self._wizard_data, 'script_path').props("outlined").classes("w-full")

            # Phase configuration
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Phase Configuration").classes("font-semibold text-lg mb-4")

                    ui.label("Select a phase template or edit phases below:").classes("mb-2")
                    self._step3_elements['phase_template'] = ui.select(
                        list(self._phase_templates.keys()),
                        with_input=False
                    ).props("outlined dense").classes("w-full")
                    self._step3_elements['phase_template'].on(
                        'update:model-value',
                        lambda e: self._apply_phase_template(e.args[0])
                    )

                    phases_json = json.dumps(self._wizard_data['phases'], indent=2)
                    self._step3_elements['phases'] = ui.textarea(
                        value=phases_json
                    ).props("outlined rows=6 class=mt-4")
                    self._step3_elements['phases'].on(
                        'blur',
                        lambda e: self._update_phase_data(self._step3_elements['phases'].value)
                    )

    def _render_step4(self) -> None:
        """Render step 4: Review and confirmation."""
        ui.label("Review experiment configuration before creation").classes("text-lg mb-4")
        
        self._step4_elements['review_container'] = ui.column().classes("gap-4 w-full")
        self._update_review_display()

    def _regenerate_experiment_id(self) -> None:
        """Generate a new experiment ID."""
        new_id = self._generate_experiment_id()
        self._wizard_data['experiment_id'] = new_id
        if 'experiment_id' in self._step1_elements:
            self._step1_elements['experiment_id'].set_value(new_id)

    def _toggle_sensor(self, sensor_id: str, checked: bool) -> None:
        """Toggle sensor selection."""
        if checked and sensor_id not in self._wizard_data['sensor_ids']:
            self._wizard_data['sensor_ids'].append(sensor_id)
        elif not checked and sensor_id in self._wizard_data['sensor_ids']:
            self._wizard_data['sensor_ids'].remove(sensor_id)

    def _toggle_controller(self, controller_id: str, checked: bool) -> None:
        """Toggle controller selection."""
        if checked and controller_id not in self._wizard_data['controller_ids']:
            self._wizard_data['controller_ids'].append(controller_id)
        elif not checked and controller_id in self._wizard_data['controller_ids']:
            self._wizard_data['controller_ids'].remove(controller_id)

    def _open_sensor_wizard(self) -> None:
        """Open the sensor setup wizard."""
        try:
            from src.gui.gui_elements.gui_sensor_setup_wizard_element import SensorSetupWizardComponent
            
            if self.sensor_manager:
                sensor_wizard = SensorSetupWizardComponent(
                    config_service=self.config_service,
                    sensor_manager=self.sensor_manager,
                    on_close=self._on_sensor_wizard_close
                )
                sensor_wizard.show_dialog()
        except Exception as e:
            error(f"Failed to open sensor wizard: {e}")
            ui.notify("Failed to open sensor wizard", color="negative")

    def _on_sensor_wizard_close(self) -> None:
        """Handle sensor wizard close callback."""
        # Reload available sensors
        self._load_available_sources()
        # Refresh step 2 display if needed
        ui.notify("Sensor configuration updated. Please review your selections.", color="info")

    def _apply_phase_template(self, template_name: Optional[str]) -> None:
        """Apply a predefined phase template to the wizard data."""
        if not template_name or template_name not in self._phase_templates:
            return

        phases = self._phase_templates[template_name]['phases']
        self._wizard_data['phases'] = [dict(p) for p in phases]

        if 'phases' in self._step3_elements:
            self._step3_elements['phases'].value = json.dumps(self._wizard_data['phases'], indent=2)
        self._update_review_display()

    def _update_phase_data(self, json_text: str) -> None:
        """Parse phase configuration from JSON text area."""
        if not json_text:
            self._wizard_data['phases'] = []
            return
        try:
            phases = json.loads(json_text)
            if isinstance(phases, list):
                self._wizard_data['phases'] = phases
                self._update_review_display()
        except json.JSONDecodeError as e:
            warning(f"Failed to parse phases: {e}")

    def _validate_and_next_step3(self) -> None:
        """Handle leaving step 3 by parsing phase data."""
        if 'phases' in self._step3_elements:
            self._update_phase_data(self._step3_elements['phases'].value)
        if self._stepper:
            self._stepper.next()

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
                        ui.label(f"Experiment ID: {self._wizard_data['experiment_id']}").classes("font-mono")
                        ui.label(f"Name: {self._wizard_data['name'] or 'Not specified'}")
                        ui.label(f"Description: {self._wizard_data['description'] or 'Not specified'}")
                        
                        if self._wizard_data['duration_enabled'] and self._wizard_data['duration_minutes']:
                            ui.label(f"Duration: {self._wizard_data['duration_minutes']} minutes")
                        else:
                            ui.label("Duration: Unlimited")
            
            # Data Sources
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Data Sources").classes("text-lg font-semibold mb-2")
                    
                    with ui.column().classes("gap-2"):
                        # Sensors
                        auto_start_sensors = "Yes" if self._wizard_data['auto_start_sensors'] else "No"
                        ui.label(f"Auto-start sensors: {auto_start_sensors}")
                        
                        if self._wizard_data['sensor_ids']:
                            ui.label(f"Selected sensors: {', '.join(self._wizard_data['sensor_ids'])}")
                        else:
                            ui.label("Sensors: All configured sensors")
                        
                        # Controllers
                        auto_start_controllers = "Yes" if self._wizard_data['auto_start_controllers'] else "No"
                        ui.label(f"Auto-start controllers: {auto_start_controllers}")
                        
                        if self._wizard_data['controller_ids']:
                            ui.label(f"Selected controllers: {', '.join(self._wizard_data['controller_ids'])}")
                        else:
                            ui.label("Controllers: All configured controllers")
            
            # Parameters
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Parameters").classes("text-lg font-semibold mb-2")
                    
                    with ui.column().classes("gap-1"):
                        ui.label(f"Data collection interval: {self._wizard_data['data_collection_interval_ms']}ms")
                        ui.label(f"Auto-save interval: {self._wizard_data['auto_save_interval_minutes']} minutes")
                        ui.label(f"Auto-compress results: {'Yes' if self._wizard_data['auto_compress'] else 'No'}")
                        ui.label(f"Enable logging: {'Yes' if self._wizard_data['enable_logging'] else 'No'}")
                        
                        if self._wizard_data['enable_logging']:
                            ui.label(f"Log level: {self._wizard_data['log_level']}")
                        
                        ui.label(f"Enable notifications: {'Yes' if self._wizard_data['enable_notifications'] else 'No'}")
                        
                        if self._wizard_data['script_path']:
                            ui.label(f"Script path: {self._wizard_data['script_path']}")

                        if self._wizard_data['phases']:
                            phase_names = ', '.join(p.get('name', '?') for p in self._wizard_data['phases'])
                            ui.label(f"Phases: {phase_names}")

    def _validate_and_next_step1(self) -> None:
        """Validate step 1 configuration and proceed to next step."""
        errors = []
        
        if not self._wizard_data['name'].strip():
            errors.append("Experiment name is required")
        
        if self._wizard_data['duration_enabled'] and not self._wizard_data['duration_minutes']:
            errors.append("Duration must be specified when duration is enabled")
        
        if errors:
            ui.notify("; ".join(errors), color="negative")
            return
            
        if self._stepper:
            self._stepper.next()

    def _parse_custom_parameters(self) -> Dict[str, Any]:
        """Parse custom parameters from JSON string."""
        if 'custom_parameters' not in self._step3_elements:
            return {}
            
        custom_params_text = self._step3_elements['custom_parameters'].value
        if not custom_params_text or not custom_params_text.strip():
            return {}
        
        try:
            return json.loads(custom_params_text)
        except json.JSONDecodeError as e:
            warning(f"Failed to parse custom parameters: {e}")
            return {}

    def _create_experiment(self) -> None:
        """Create the experiment with the configured settings."""
        self._create_experiment_internal(start_immediately=False)

    def _create_and_start_experiment(self) -> None:
        """Create and immediately start the experiment."""
        self._create_experiment_internal(start_immediately=True)

    def _create_experiment_internal(self, start_immediately: bool = False) -> None:
        """Internal method to create experiment with optional immediate start."""
        try:
            if not self.experiment_manager:
                raise RuntimeError("Experiment manager not available")
            
            # Validate required fields
            if not self._wizard_data['experiment_id']:
                ui.notify("Experiment ID is required", color="negative")
                return
                
            if not self._wizard_data['name'].strip():
                ui.notify("Experiment name is required", color="negative")
                return
            
            # Parse custom parameters
            custom_parameters = self._parse_custom_parameters()
            
            # Create experiment configuration
            duration_minutes = None
            if self._wizard_data['duration_enabled'] and self._wizard_data['duration_minutes']:
                duration_minutes = int(self._wizard_data['duration_minutes'])
            
            experiment_config = ExperimentConfig(
                name=self._wizard_data['name'].strip(),
                description=self._wizard_data['description'].strip(),
                duration_minutes=duration_minutes,
                auto_start_sensors=bool(self._wizard_data['auto_start_sensors']),
                auto_start_controllers=bool(self._wizard_data['auto_start_controllers']),
                sensor_ids=list(self._wizard_data['sensor_ids']),
                controller_ids=list(self._wizard_data['controller_ids']),
                data_collection_interval_ms=int(self._wizard_data['data_collection_interval_ms']),
                auto_compress=bool(self._wizard_data['auto_compress']),
                custom_parameters=custom_parameters,
                script_path=self._wizard_data.get('script_path') or None,
                phases=list(self._wizard_data['phases'])
            )
            
            # Create experiment
            experiment_id = self.experiment_manager.create_experiment(experiment_config)
            
            if start_immediately:
                # Start experiment asynchronously
                import asyncio
                asyncio.create_task(self._start_experiment_async(experiment_id))
                ui.notify(f'Experiment "{experiment_config.name}" created and starting...', color='positive')
            else:
                ui.notify(f'Experiment "{experiment_config.name}" created successfully', color='positive')
            
            info(f"Created experiment configuration: {experiment_id}")
            
            # Close dialog and notify parent
            self._close_dialog()
            
        except Exception as e:
            error(f"Failed to create experiment: {e}")
            ui.notify(f"Failed to create experiment: {str(e)}", color="negative")

    async def _start_experiment_async(self, experiment_id: str) -> None:
        """Start experiment asynchronously."""
        
        try:
            if not self.experiment_manager:
                notify_later('Experiment manager not available', color='negative', slot=self._dialog)
                return
                
            success = await self.experiment_manager.start_experiment(experiment_id)
            if success:
                notify_later('Experiment started successfully', color='positive', slot=self._dialog)
            else:
                notify_later('Failed to start experiment', color='negative', slot=self._dialog)
        except Exception as e:
            error(f"Error starting experiment: {e}")
            notify_later(f'Error starting experiment: {str(e)}', color='negative', slot=self._dialog)



# Legacy compatibility class - redirect to new wizard
class SetupWizardComponent(ExperimentSetupWizardComponent):
    """Legacy compatibility wrapper for ExperimentSetupWizardComponent."""
    
    def __init__(self, config_service, experiment_manager, sensor_manager=None, controller_manager=None):
        super().__init__(config_service, experiment_manager, sensor_manager, controller_manager)
        
    def show_dialog(self, start_step: str = "experiments", on_close: Optional[Callable[[], None]] = None) -> None:
        """Legacy compatibility method."""
        if start_step == "experiments":
            super().show_dialog()
        else:
            # For non-experiment steps, show the original simple wizard
            self._show_legacy_wizard(start_step)
            
    def _show_legacy_wizard(self, start_step: str) -> None:
        """Show simplified legacy wizard for non-experiment steps."""
        with ui.dialog().props("persistent") as dialog:
            self._dialog = dialog
            with ui.card().classes("w-[600px] max-w-[90vw]"):
                ui.label("Setup Wizard").classes("text-xl font-bold mb-4")
                ui.label("This wizard will be expanded in future versions.").classes("mb-4")
                
                with ui.row().classes("gap-2 justify-end"):
                    ui.button("Close", on_click=dialog.close).props("flat")
        
        dialog.open()
